#!/usr/bin/env python3
"""threewalks.py -- the same disc counted by three different walkers.

The briefing for this session handed down "857 files in 25 folders" as *the*
file count of the disc. That number came from a Windows walk of the mounted
volume. This tool exists because a file count is not a property of a disc, it
is a property of a walker, and this disc carries three walkers' worth of
catalogue:

  Windows      what os.walk() sees on the mounted volume, i.e. the Joliet
               namespace as filtered by the Windows CDFS driver
  ISO 9660     the directory records of the primary descriptor, read directly
  Joliet       the directory records of the supplementary descriptor
  HFS          the catalogue B-tree of the Apple partition

It prints all four, subtracts them pairwise, and -- the part that matters --
names every file that one walker has and another does not, so that the
difference is a list and not a number.

    python tools/threewalks.py --tree _work/iso \\
        --image _work/clic11.img --hfs notes/hfs-files.tsv

"""
import argparse
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import assoc


def load_namespace(image, joliet):
    """the directory records themselves, via assoc.py, split by the
    Associated-File flag.

    The first version of this function read back an isodev.py --extents
    listing with a regular expression and put the result in a dict. Eighteen
    records vanished into key collisions -- the resource forks, which carry
    the same path as their data fork -- and the tool printed 857 where the
    volume has 875. Reading the records is both shorter and correct, and the
    two halves are returned separately so that they can never be merged by
    accident again.
    """
    img = assoc.Img(image)
    want = 2 if joliet else 1
    vd = None
    for n in range(16, 32):
        s = img.sector(n)
        if s is None or s[1:6] != b"CD001":
            continue
        if s[0] == want:
            vd = s
            break
        if s[0] == 255:
            break
    if vd is None:
        raise SystemExit("no descriptor of type %d in %s" % (want, image))
    root = vd[156:190]
    recs = assoc.walk(img, struct.unpack("<I", root[2:6])[0],
                      struct.unpack("<I", root[10:14])[0], joliet)
    data = {r[0]: (r[1], r[2]) for r in recs
            if not (r[3] & 2) and not (r[3] & 4)}
    rsrc = {r[0]: (r[1], r[2]) for r in recs if not (r[3] & 2) and (r[3] & 4)}
    return data, rsrc


def load_tree(root):
    out = {}
    for dp, dn, fn in os.walk(root):
        for f in fn:
            p = os.path.join(dp, f)
            rel = os.path.relpath(p, root).replace(os.sep, "/")
            out[rel] = os.path.getsize(p)
    return out


def load_hfs(path):
    out = {}
    with open(path, encoding="utf-8", newline="") as fh:
        hdr = fh.readline().rstrip("\n").split("\t")
        ip = hdr.index("path")
        il = hdr.index("data_len")
        for line in fh:
            c = line.rstrip("\n").split("\t")
            if len(c) <= max(ip, il):
                continue
            p = c[ip]
            p = p.split("/", 1)[1] if "/" in p else p
            out[p] = int(c[il])
    return out


def norm(p):
    return p.upper().replace(" ", "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--tree", default="_work/iso")
    ap.add_argument("--image", default="_work/clic11.img")
    ap.add_argument("--hfs", default="notes/hfs-files.tsv")
    a = ap.parse_args()

    win = load_tree(a.tree)
    iso, iso_r = load_namespace(a.image, False)
    jol, jol_r = load_namespace(a.image, True)
    hfs = load_hfs(a.hfs)

    print("walker                                        files          bytes")
    print("  Windows, os.walk of the mounted volume  %8d %14d"
          % (len(win), sum(win.values())))
    print("  ISO 9660 primary directory records      %8d %14d"
          % (len(iso), sum(v[1] for v in iso.values())))
    print("  Joliet supplementary directory records  %8d %14d"
          % (len(jol), sum(v[1] for v in jol.values())))
    print()
    print("  ISO records carrying the Associated-File flag (resource forks)")
    print("    primary namespace                     %8d %14d"
          % (len(iso_r), sum(v[1] for v in iso_r.values())))
    print("    Joliet namespace                      %8d %14d"
          % (len(jol_r), sum(v[1] for v in jol_r.values())))
    print("    all ISO file records                  %8d %14d"
          % (len(iso) + len(iso_r),
             sum(v[1] for v in iso.values()) + sum(v[1] for v in iso_r.values())))
    print("  HFS catalogue, data forks only          %8d %14d"
          % (len(hfs), sum(hfs.values())))

    wn = {norm(k): k for k in win}
    jn = {norm(k): k for k in jol}
    only_j = sorted(set(jn) - set(wn))
    only_w = sorted(set(wn) - set(jn))
    print()
    print("Joliet minus Windows : %d records the driver did not hand over"
          % len(only_j))
    for k in only_j:
        print("   %-56s %10d bytes" % (jn[k], jol[jn[k]][1]))
    print()
    print("Windows minus Joliet : %d" % len(only_w))
    for k in only_w:
        print("   %s" % wn[k])
    print()

    dupes = {}
    for k in jol:
        dupes.setdefault(norm(k), []).append(k)
    coll = {k: v for k, v in dupes.items() if len(v) > 1}
    print("Joliet names that collide once folded to upper case and de-spaced : %d"
          % len(coll))
    for k, v in sorted(coll.items()):
        print("   %s" % " | ".join(v))
    print()

    hn = {norm(k): k for k in hfs}
    print("HFS minus Joliet     : %d" % len(set(hn) - set(jn)))
    for k in sorted(set(hn) - set(jn)):
        print("   %-56s %10d bytes" % (hn[k], hfs[hn[k]]))
    print()
    print("Joliet minus HFS     : %d" % len(set(jn) - set(hn)))
    print("in both              : %d" % len(set(jn) & set(hn)))


if __name__ == "__main__":
    main()
