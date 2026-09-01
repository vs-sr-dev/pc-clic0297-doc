#!/usr/bin/env python3
"""compare.py -- the rebuilt image against the disc it was rebuilt from.

This repository has two copies of one product: a 2003 ISO image made with
WinISO, and the pressed disc itself. Everything the image says about who made
the game and when is contaminated by the intermediate step, and the only way
to measure the contamination is to put the two side by side.

Compares, per file, by SHA-1 over the file contents, and separately compares
the filesystem metadata that the two disagree about. Read errors on the
physical disc are reported rather than swallowed: a scratched disc that
cannot be read is a fact about the disc, not a reason to print nothing.

    python tools/compare.py IMAGE.iso E:
    python tools/compare.py IMAGE.iso E: --meta      # metadata only, fast
"""
import hashlib
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import iso9660 as I  # noqa: E402


def index(path):
    fh, mm = I.open_image(path)
    vds = I.read_vds(mm)
    tree = I.tree_of(mm, vds, True)
    out = {}
    for e in tree:
        if e["isdir"]:
            continue
        key = (e["path"] + e["name"]).lstrip("/").lower()
        # Nero writes the ISO 9660 ';1' version suffix into the Joliet names
        # too; WinISO strips it. Keys are compared without it.
        if ";" in key:
            key = key.split(";")[0]
        out[key] = e
    return fh, mm, vds, tree, out


def sha1_of(mm, e):
    h = hashlib.sha1()
    off = e["extent"] * 2048
    rem = e["size"]
    while rem > 0:
        n = min(rem, 1 << 20)
        h.update(mm[off:off + n])
        off += n
        rem -= n
    return h.hexdigest()


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if len(sys.argv) < 3:
        raise SystemExit(__doc__)
    a_path, b_path = sys.argv[1], sys.argv[2]
    fa, ma, vda, ta, A = index(a_path)
    fb, mb, vdb, tb, B = index(b_path)

    print("=== A: %s" % a_path)
    print("=== B: %s" % b_path)
    print()
    pa = [b for s, t, b in vda if t == 1][0]
    pb = [b for s, t, b in vdb if t == 1][0]
    import struct
    rows = [
        ("declared volume sectors",
         struct.unpack_from("<I", pa, 80)[0],
         struct.unpack_from("<I", pb, 80)[0]),
        ("declared volume bytes",
         struct.unpack_from("<I", pa, 80)[0] * 2048,
         struct.unpack_from("<I", pb, 80)[0] * 2048),
        ("L path table sector",
         struct.unpack_from("<I", pa, 140)[0],
         struct.unpack_from("<I", pb, 140)[0]),
        ("M path table sector",
         struct.unpack_from(">I", pa, 148)[0],
         struct.unpack_from(">I", pb, 148)[0]),
        ("root directory extent",
         struct.unpack_from("<I", pa, 158)[0],
         struct.unpack_from("<I", pb, 158)[0]),
        ("files", len(A), len(B)),
        ("file bytes", sum(e["size"] for e in A.values()),
         sum(e["size"] for e in B.values())),
    ]
    print("%-28s %18s %18s %s" % ("field", "A", "B", ""))
    for name, x, y in rows:
        print("%-28s %18s %18s %s" % (
            name, x, y, "" if x == y else "  <-- differ"))
    for label, lo, hi in (("publisher identifier", 318, 446),
                          ("data preparer identifier", 446, 574),
                          ("application identifier", 574, 702)):
        x = bytes(pa[lo:hi]).rstrip(b" \x00").decode("latin-1")
        y = bytes(pb[lo:hi]).rstrip(b" \x00").decode("latin-1")
        print("%-28s %18r %18r %s" % (
            label, x, y, "" if x == y else "  <-- differ"))
    for i, lab in enumerate(("creation", "modification")):
        x = bytes(pa[813 + i * 17:813 + i * 17 + 16]).decode("latin-1")
        y = bytes(pb[813 + i * 17:813 + i * 17 + 16]).decode("latin-1")
        ox = struct.unpack_from("b", pa, 813 + i * 17 + 16)[0]
        oy = struct.unpack_from("b", pb, 813 + i * 17 + 16)[0]
        print("%-28s %14s%+3d %14s%+3d %s" % (
            lab + " date", x, ox, y, oy, "" if x == y else "  <-- differ"))
    ka, kb = set(A), set(B)
    print()
    print("paths in A only : %d" % len(ka - kb))
    for p in sorted(ka - kb)[:20]:
        print("    %s" % p)
    print("paths in B only : %d" % len(kb - ka))
    for p in sorted(kb - ka)[:20]:
        print("    %s" % p)
    both = sorted(ka & kb)
    print("paths in both   : %d" % len(both))

    sized = [p for p in both if A[p]["size"] != B[p]["size"]]
    print("differing in size: %d" % len(sized))
    for p in sized[:20]:
        print("    %s  A=%d B=%d" % (p, A[p]["size"], B[p]["size"]))

    datediff = [p for p in both if A[p]["raw7"] != B[p]["raw7"]]
    print("differing in recorded date: %d of %d (%.2f %%)" % (
        len(datediff), len(both),
        100.0 * len(datediff) / max(len(both), 1)))
    ta_set = set(e["raw7"] for e in A.values())
    tb_set = set(e["raw7"] for e in B.values())
    print("distinct file timestamps, A: %d   B: %d" % (
        len(ta_set), len(tb_set)))
    print("A timestamps that are valid dates: %d of %d" % (
        sum(1 for t in ta_set if I.date_is_valid(t)), len(ta_set)))
    print("B timestamps that are valid dates: %d of %d" % (
        sum(1 for t in tb_set if I.date_is_valid(t)), len(tb_set)))

    if "--meta" in sys.argv:
        return

    print()
    print("hashing %d files in both..." % len(both))
    same = diff = err = 0
    errors = []
    diffs = []
    done = 0
    for p in both:
        try:
            ha = sha1_of(ma, A[p])
            hb = sha1_of(mb, B[p])
        except Exception as ex:
            err += 1
            errors.append((p, "%s: %s" % (type(ex).__name__, ex)))
            continue
        if ha == hb:
            same += 1
        else:
            diff += 1
            diffs.append((p, ha, hb, A[p]["size"]))
        done += 1
        if done % 400 == 0:
            sys.stderr.write("  %d/%d\n" % (done, len(both)))
    print()
    print("byte-identical      : %d" % same)
    print("differing contents  : %d" % diff)
    print("unreadable          : %d" % err)
    for p, ha, hb, n in diffs[:40]:
        print("    DIFFERS %9d  %s" % (n, p))
        print("       A %s" % ha)
        print("       B %s" % hb)
    for p, why in errors[:40]:
        print("    UNREADABLE %s  --  %s" % (p, why))
    if hasattr(mb, "errors") and mb.errors:
        print()
        print("physical sectors that would not read: %d" % len(mb.errors))
        print("    %s" % sorted(mb.errors)[:40])


if __name__ == "__main__":
    main()
