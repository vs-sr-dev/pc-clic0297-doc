#!/usr/bin/env python3
"""collectrefs.py -- harvest every filename-shaped string the product says.

This feeds `resolve.py` and is not a measurement in itself. It walks the five
Director containers' literal pools and name tables, plus the disc's plain-text
configuration files, keeps anything shaped like a filename, and writes the list
out. `resolve.py` then answers whether each one exists on the disc and in what
case.

The two are separate because the harvesting is specific to this disc's five
containers and the resolving is not. Splitting them also means the list of
things the product claims to reference is itself a committed artefact
(`notes/refs-collected.txt`) that can be read and argued with, rather than an
intermediate that only exists inside one tool's memory.

    python tools/collectrefs.py 883 notes/refs-collected.txt
"""
import os
import re
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import director  # noqa: E402

try:
    sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
except (AttributeError, ValueError):
    pass

ROOT = sys.argv[1] if len(sys.argv) > 1 else "883"
DEST = sys.argv[2] if len(sys.argv) > 2 else os.path.join("notes",
                                                          "refs-collected.txt")

EXT = re.compile(
    r"\.(mov|dxr|dir|swf|x32|exe|jpg|jpeg|ivr|bmp|txt|ini|inf|dat|cab|sea"
    r"|html?|url|dll|wav|rwx|seq|awm|awh)$", re.I)

CONTAINERS = ("dati/SLOT.DXR", "dati/VRMAC.DXR", "dati/menuDir7.dxr",
              "883.exe", "dati/VR.EXE")

TEXTFILES = ("LEGGIMI.TXT", "AUTORUN.INF", "dati/install/autorun.inf",
             "dati/install/win32/locale.ini",
             "dati/install/win32/it/iesetup.ini",
             "dati/install/win32/it/bin/iecd.ini",
             "dati/install/win32/it/bin/closeie.isk",
             "dati/install/win32/it/bin/icw.isk",
             "dati/install/win32/it/bin/isp.isk",
             "dati/Vrmedia/Monaco01.ivr", "dati/Vrmedia/Monaco05.ivr",
             "dati/Vrmedia/Monaco06.ivr", "dati/Vrmedia/monaco07.ivr",
             "dati/Vrmedia/monaco08.ivr")

SEP = chr(92)          # backslash, written this way so no escaping is involved
TOKEN = re.compile("[A-Za-z0-9_.:/~-]+|[A-Za-z0-9_.:/~" + re.escape(SEP) + "-]+")


def main():
    names = set()

    # 1. Director literal pools and name tables, including projector overlays
    for rel in CONTAINERS:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        data = open(path, "rb").read()
        hits = director.find_overlays(data)
        base = hits[0][0] if data[:2] == b"MZ" and hits else 0
        r = director.Reader(data, base)
        for s in r.scripts():
            for lit in s["literals"]:
                t = lit.decode("latin-1").strip()
                if EXT.search(t):
                    names.add(t)
        for cid, count, got in r.names():
            for n in got:
                t = n.decode("latin-1").strip()
                if EXT.search(t):
                    names.add(t)

    # 2. the disc's own plain-text configuration and readme files
    for rel in TEXTFILES:
        path = os.path.join(ROOT, rel.replace("/", os.sep))
        if not os.path.exists(path):
            continue
        txt = open(path, "rb").read().decode("cp1252", errors="replace")
        for tok in TOKEN.findall(txt):
            tok = tok.strip()
            if not EXT.search(tok):
                continue
            if SEP in tok or "/" in tok:
                tok = tok.replace(SEP, "/").rsplit("/", 1)[-1]
            names.add(tok)

    out = sorted(names, key=str.lower)
    d = os.path.dirname(DEST)
    if d and not os.path.isdir(d):
        os.makedirs(d)
    with open(DEST, "w", encoding="utf-8") as fh:
        fh.write("# Filename-shaped strings harvested from the Director literal\n")
        fh.write("# pools and name tables of SLOT.DXR, VRMAC.DXR, menuDir7.dxr,\n")
        fh.write("# 883.exe and VR.EXE, plus the disc's plain-text config files.\n")
        fh.write("# Collected by tools/collectrefs.py; resolved by tools/resolve.py.\n")
        fh.write("\n")
        for n in out:
            fh.write(n + "\n")

    print("collected %d filename-shaped strings -> %s" % (len(out), DEST))
    for n in out:
        print("  " + n)


if __name__ == "__main__":
    main()
