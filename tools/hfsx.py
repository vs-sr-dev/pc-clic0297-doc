#!/usr/bin/env python3
"""hfsx.py -- extract forks from the HFS volume that Windows will not mount.

twofs.py names the 28 files that exist only in the HFS catalogue and the 17 that
carry a resource fork. Naming them is not measuring them: the Macintosh
application, the ten Xtras and the seven Director files on the Mac side cannot
be censused until their bytes are somewhere a reader can open them.

This extracts by **address**, never by search: a file's forks are read from the
extents in its catalog record, in order, for exactly its logical length. A fork
that needs more than the three extents in the record would have to be completed
from the extents overflow file, and the tool says so loudly rather than handing
back a short file that looks whole.

    python tools/hfsx.py E --list
    python tools/hfsx.py E --only-hfs --out _work/hfs
    python tools/hfsx.py E --rsrc --out _work/hfs
    python tools/hfsx.py E --path "Sellerio/Il Cane di Terracotta" --out _work/hfs

WHAT A "FILE" BECOMES ON A FILESYSTEM THAT HAS NO FORKS
------------------------------------------------------
The destination is NTFS, which has no resource forks, so one HFS file can become
two files here. The data fork keeps the name; the resource fork gets `.rsrc`
appended. That is a decision of this tool and not a property of the disc, and it
is why the counts printed at the end distinguish *files extracted* from *forks
written*. A name that ends in the carriage return an HFS name may legally contain
is escaped the same way hfs.py escapes it, because NTFS will not take it.
"""
import argparse
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import hfs as H


def safe(name):
    out = []
    for ch in name:
        o = ord(ch)
        if o < 0x20 or o == 0x7f or ch in '<>:"|?*\\':
            out.append("%%%02x" % o)
        else:
            out.append(ch)
    return "".join(out)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive", nargs="?", default="E")
    ap.add_argument("--image")
    ap.add_argument("--cache", default="_work/raw")
    ap.add_argument("--out", default="_work/hfs")
    ap.add_argument("--list", action="store_true")
    ap.add_argument("--only-hfs", action="store_true",
                    help="extract the files whose path has no ISO counterpart")
    ap.add_argument("--iso", default="_work/iso")
    ap.add_argument("--rsrc", action="store_true",
                    help="also extract every non-empty resource fork on the volume")
    ap.add_argument("--path", action="append", default=[])
    a = ap.parse_args()

    src = H.Source(drive=a.drive, image=a.image, cache=a.cache)
    part, pm = H.find_hfs(src)
    if part is None:
        print("no Apple_HFS partition")
        return
    vol = H.Volume(src, part)
    cat = vol.catalog()
    hdr, recs = H.parse_catalog(cat)
    dirs, path_of = H.build_paths(recs)

    files = []
    for r in recs:
        if r["type"] != "file":
            continue
        f = H.filrec(r["data"])
        full = path_of(r["parent"]) + "/" + r["name"]
        i = full.find("/")
        rel = full[i + 1:] if i >= 0 else ""
        files.append((rel, f))

    isoset = set()
    if a.only_hfs:
        for dp, dn, fn in os.walk(a.iso):
            for n in fn:
                p = os.path.relpath(os.path.join(dp, n), a.iso)
                isoset.add(p.replace(os.sep, "/").lower())

    want = []
    for rel, f in files:
        if a.path:
            if rel in a.path:
                want.append((rel, f))
            continue
        if a.only_hfs and rel.lower() not in isoset:
            want.append((rel, f))
        elif a.rsrc and f["rsrc_len"] > 0 and not a.only_hfs:
            want.append((rel, f))

    if a.list:
        print("%-6s %-5s %-5s %10s %10s %-14s  %s"
              % ("cnid", "type", "creat", "data", "rsrc", "data extents", "path"))
        for rel, f in sorted(want):
            de = ";".join("%d+%d" % e for e in f["data_extents"] if e[1])
            print("%-6d %-5s %-5s %10d %10d %-14s  %s"
                  % (f["id"], f["type"], f["creator"], f["data_len"],
                     f["rsrc_len"], de, H.escname(rel)))
        print()
        print("%d files" % len(want))
        return

    nfiles = nforks = nbytes = 0
    short = []
    for rel, f in sorted(want):
        dest = os.path.join(a.out, *[safe(p) for p in H.escname(rel).split("/")])
        try:
            os.makedirs(os.path.dirname(dest))
        except OSError:
            pass
        nfiles += 1
        for tag, ln, ext in (("data", f["data_len"], f["data_extents"]),
                             ("rsrc", f["rsrc_len"], f["rsrc_extents"])):
            if ln == 0:
                continue
            cap = sum(c for s, c in ext) * vol.ablk
            if cap < ln:
                short.append((rel, tag, ln, cap))
            b = vol.read_extents(ext, ln)
            p = dest if tag == "data" else dest + ".rsrc"
            with open(p, "wb") as fo:
                fo.write(b)
            nforks += 1
            nbytes += len(b)

    print("extracted %d files, %d forks, %d bytes into %s"
          % (nfiles, nforks, nbytes, a.out))
    if short:
        print()
        print("!! %d forks declare more bytes than their three catalog extents"
              " can hold." % len(short))
        print("   Those need the extents overflow file and are SHORT here:")
        for rel, tag, ln, cap in short:
            print("   %s [%s] wants %d, extents hold %d" % (rel, tag, ln, cap))
    else:
        print("every fork fitted in the three extents of its catalog record;")
        print("none needed the extents overflow file.")
    print()
    print("[source: %s   sector reads issued %d, served from cache %d]"
          % (a.image or H.devpath(a.drive), src.reads, src.cached))


if __name__ == "__main__":
    main()
