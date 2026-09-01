#!/usr/bin/env python3
"""pecensus.py -- one line per binary across a whole tree.

`pe.py` prints everything about one file, which is what you want when there is
one file. This tree has eighteen `.exe`, three `.x32` and one 16-bit `NE`, and
the question is not "what is in this binary" but "how do these binaries relate
to each other" -- which linker, which timestamp, whose company name, and do the
timestamps cluster into build days.

It reuses `pe.py`'s parser rather than reimplementing it, falls back to `ne.py`
for 16-bit files, and prints the COFF timestamp beside the filesystem mtime so
the two clocks can be read on one line.

    python tools/pecensus.py DIR
    python tools/pecensus.py DIR --ext .exe .dll .x32
    python tools/pecensus.py DIR --sort coff
"""
import argparse
import datetime
import os
import struct
import sys

HERE = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, HERE)

import pe as pemod            # noqa: E402
import ne as nemod            # noqa: E402


def version_field(vi, key):
    """Pull one VS_VERSIONINFO string out of pe.py's harvested run list.

    pe.py returns the version block as a flat list of printable UTF-16 runs, in
    file order, so a value is simply the run after its key. Two things make a
    naive lookup wrong and are handled here:

      * the block is emitted twice, once per language sub-block (040904b0 and
        040904E4 on the Macromedia binaries), so the same key appears more than
        once. The first non-empty value wins;
      * padding between a key and its value sometimes produces a short junk run
        (Director's blocks contain runs like "r'"), so a candidate that is
        itself a known key name is skipped.
    """
    if not vi:
        return ""
    strings = vi.get("strings") or []
    KEYS = set(["CompanyName", "FileDescription", "FileVersion", "InternalName",
                "LegalCopyright", "LegalTrademarks", "OriginalFilename",
                "ProductName", "ProductVersion", "Comments", "VarFileInfo",
                "Translation", "StringFileInfo", "VS_VERSION_INFO"])
    for i, s in enumerate(strings):
        if s != key:
            continue
        for j in range(i + 1, min(i + 4, len(strings))):
            cand = strings[j]
            if cand in KEYS or len(cand) < 2:
                continue
            return cand
    return ""


def signature_size(p):
    """Bytes in the PE security data directory -- i.e. is it Authenticode signed?

    Directory index 4 is IMAGE_DIRECTORY_ENTRY_SECURITY. Unlike every other
    data directory its first field is a FILE OFFSET rather than an RVA, which
    does not matter here because only the size is read: a size of zero means no
    certificate table, and any non-zero size means there is one.

    This exists because the chapter that needed it asserted "nothing on this
    disc is signed" before checking, and three files are.
    """
    d = p.data
    oh = p.e_lfanew + 24
    try:
        ndirs = struct.unpack_from("<I", d, oh + 92)[0]
        if ndirs < 5:
            return 0
        return struct.unpack_from("<I", d, oh + 96 + 4 * 8 + 4)[0]
    except Exception:
        return 0


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("dir")
    ap.add_argument("--ext", nargs="*",
                    default=[".exe", ".dll", ".x32", ".ocx", ".cpl", ".sys"])
    ap.add_argument("--sort", choices=["path", "coff", "mtime", "size"],
                    default="path")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    exts = tuple(e.lower() for e in args.ext)
    rows = []
    for dp, dn, fn in os.walk(args.dir):
        dn.sort()
        for f in sorted(fn):
            if not f.lower().endswith(exts):
                continue
            full = os.path.join(dp, f)
            rel = os.path.relpath(full, args.dir).replace(os.sep, "/")
            st = os.stat(full)
            mt = datetime.datetime.fromtimestamp(st.st_mtime)
            row = {"rel": rel, "size": st.st_size, "mtime": mt,
                   "fmt": "?", "coff": None, "linker": "", "company": "",
                   "product": "", "fileversion": "", "note": "", "signed": None}
            try:
                p = pemod.PE(full)
                row["fmt"] = "PE32" if getattr(p, "machine", 0) == 0x14C else "PE"
                row["signed"] = signature_size(p) > 0
                row["coff"] = datetime.datetime(1970, 1, 1) + \
                    datetime.timedelta(seconds=p.timestamp)
                row["linker"] = "%d.%02d" % p.linker
                vi = p.versioninfo()
                row["company"] = version_field(vi, "CompanyName")
                row["product"] = version_field(vi, "ProductName")
                row["fileversion"] = version_field(vi, "FileVersion")
            except Exception as exc:
                try:
                    n = nemod.NE(full)
                    row["fmt"] = "NE16"
                    row["linker"] = "%d.%02d" % (n.ver, n.rev)
                    res = n.resident_names()
                    nres = n.nonresident_names()
                    row["product"] = res[0][0].decode("latin-1") if res else ""
                    row["company"] = nres[0][0].decode("latin-1") if nres else ""
                    row["note"] = "16-bit"
                except Exception as exc2:
                    row["fmt"] = "n/a"
                    row["note"] = str(exc).split(":")[0][:40]
            rows.append(row)

    keys = {"path": lambda r: r["rel"],
            "coff": lambda r: (r["coff"] or datetime.datetime(1970, 1, 1)),
            "mtime": lambda r: r["mtime"],
            "size": lambda r: -r["size"]}
    rows.sort(key=keys[args.sort])

    print("%-46s %6s %10s %7s %-19s %-19s %s"
          % ("path", "fmt", "bytes", "linker", "COFF (UTC)", "mtime (local)",
             "CompanyName / module"))
    print("-" * 46 + " " + "-" * 6 + " " + "-" * 10 + " " + "-" * 7 + " "
          + "-" * 19 + " " + "-" * 19 + " " + "-" * 30)
    for r in rows:
        print("%-46s %6s %10d %7s %-19s %-19s %s"
              % (r["rel"][-46:], r["fmt"], r["size"], r["linker"],
                 r["coff"].strftime("%Y-%m-%d %H:%M:%S") if r["coff"] else "-",
                 r["mtime"].strftime("%Y-%m-%d %H:%M:%S"),
                 (r["company"] or r["note"])[:34]))

    print()
    print("=== files whose mtime PRECEDES their own COFF link timestamp ===")
    print("(a file cannot be written before it is linked; where this happens")
    print(" the mtime is synthetic, or the two clocks are in different zones)")
    print()
    bad = []
    for r in rows:
        if not r["coff"]:
            continue
        delta = (r["mtime"] - r["coff"]).total_seconds()
        if delta < 0:
            bad.append((r, delta))
    if not bad:
        print("    none")
    else:
        print("%-46s %-19s %-19s %s"
              % ("path", "COFF (UTC)", "mtime (local)", "mtime - COFF"))
        for r, delta in bad:
            h = delta / 3600.0
            print("%-46s %-19s %-19s %10.0f s = %+.2f h"
                  % (r["rel"][-46:],
                     r["coff"].strftime("%Y-%m-%d %H:%M:%S"),
                     r["mtime"].strftime("%Y-%m-%d %H:%M:%S"), delta, h))
    print()
    print("impossible mtimes : %d of %d datable binaries"
          % (len(bad), sum(1 for r in rows if r["coff"])))

    print()
    print("binaries        : %d" % len(rows))
    fmts = {}
    for r in rows:
        fmts[r["fmt"]] = fmts.get(r["fmt"], 0) + 1
    print("by format       : %s"
          % ", ".join("%s %d" % (k, v) for k, v in sorted(fmts.items())))
    coffs = sorted(r["coff"] for r in rows if r["coff"])
    if coffs:
        print("COFF range      : %s .. %s"
              % (coffs[0].strftime("%Y-%m-%d"), coffs[-1].strftime("%Y-%m-%d")))
        days = sorted({c.date() for c in coffs})
        print("distinct COFF days: %d  %s"
              % (len(days), ", ".join(str(d) for d in days)))
    comps = {}
    for r in rows:
        c = r["company"] or "(none)"
        comps[c] = comps.get(c, 0) + 1
    signed = [r for r in rows if r.get("signed")]
    print()
    print("Authenticode: %d of %d PE files carry a certificate table"
          % (len(signed), sum(1 for r in rows if r["fmt"].startswith("PE"))))
    for r in signed:
        print("    SIGNED  %s" % r["rel"])
    if not signed:
        print("    none")

    print()
    print("CompanyName / module name, by count:")
    for c, n in sorted(comps.items(), key=lambda kv: -kv[1]):
        print("    %-40s %d" % (c[:40], n))


if __name__ == "__main__":
    main()
