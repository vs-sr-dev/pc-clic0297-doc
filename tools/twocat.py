#!/usr/bin/env python3
"""twocat.py -- the ownership map of a hybrid disc, walked from BOTH catalogues.

Every previous sector map in this collection (`secmap.py`, `sectormap.py`,
`gapmap.py`) assigns each sector to at most one owner, because every previous
disc had one filesystem that mattered. This disc has two and they describe the
same bytes: the ISO 9660 directory record for `/CATAL.HTM;1` and the HFS
catalogue record for `Clic!/catal.htm` point at the same LBA. A map that insists
on one owner per sector cannot describe that; it will either double-count or
silently drop one side.

So this builds a map of *how many* owners each sector has, and of which. The
classes:

    sys      sectors 0..15, the ISO system area -- which on this disc also
             holds the Apple partition map and, from LBA 138, the HFS volume
             header. Those overlaps are reported, not hidden.
    vd       volume descriptors
    ptbl     the two path tables
    isodir   ISO directory extents
    isofile  ISO file extents, INCLUDING the Associated-File records
    hfsvol   HFS boot blocks, MDB, volume bitmap, alternate MDB
    hfsbt    the HFS catalogue and extents-overflow B-tree files
    hfsfile  HFS file extents, data fork and resource fork

An ISO extent of a file of length L covers ceil(L/2048) sectors. An HFS extent
is counted in allocation blocks of drAlBlkSiz bytes and the WHOLE allocation
block is owned whether or not the file fills it -- that is the point, because
the difference between the two granularities is the thing being measured.

Addresses, never scans. filStBlk is a hint field and is zero on this volume;
the authoritative fork address is the first entry of filExtRec, as hfs.py's
--tsv already documents. A fork whose three extent slots are all used may
continue in the extents overflow file; --overflow reports how many do.

    python tools/twocat.py IMAGE
    python tools/twocat.py IMAGE --unowned
    python tools/twocat.py IMAGE --only-hfs
    python tools/twocat.py IMAGE --only-iso
    python tools/twocat.py IMAGE --align
    python tools/twocat.py IMAGE --slack-sample N
"""
import argparse
import collections
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import iso9660
import hfs

SECTOR = 2048


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--unowned", action="store_true")
    ap.add_argument("--only-hfs", action="store_true")
    ap.add_argument("--only-iso", action="store_true")
    ap.add_argument("--align", action="store_true")
    ap.add_argument("--overflow", action="store_true")
    ap.add_argument("--slack-sample", type=int, default=0)
    ap.add_argument("--dump-unowned", help="write the unowned LBA runs here")
    a = ap.parse_args()

    # ---------------------------------------------------------------- ISO side
    fh, mm = iso9660.open_image(a.image)
    vds = iso9660.read_vds(mm)
    import struct
    _sec, pvd = iso9660.pick(vds, False)
    volspace = struct.unpack_from("<I", pvd, 80)[0]
    pt_size = struct.unpack_from("<I", pvd, 132)[0]
    pt_l = struct.unpack_from("<I", pvd, 140)[0]
    pt_m = struct.unpack_from(">I", pvd, 148)[0]
    entries = iso9660.tree_of(mm, vds, False)

    size = os.path.getsize(a.image)
    total_img = size // SECTOR

    owners = [[] for _ in range(volspace)]

    def claim(lo, n, cls):
        for s in range(lo, lo + n):
            if 0 <= s < volspace:
                owners[s].append(cls)

    claim(0, 16, "sys")
    # The root directory's own extent. tree_of() walks the root's CONTENTS and
    # never emits a record for the root itself, so without this line LBA 20 is
    # reported as belonging to nobody -- which is exactly the plausible-looking
    # wrong answer this map exists to avoid.
    root_ext = struct.unpack_from("<I", pvd, 158)[0]
    root_len = struct.unpack_from("<I", pvd, 166)[0]
    claim(root_ext, max((root_len + SECTOR - 1) // SECTOR, 1), "isodir")
    for sec, t, b in vds:
        claim(sec, 1, "vd")
    ptsec = (pt_size + SECTOR - 1) // SECTOR
    claim(pt_l, ptsec, "ptbl")
    claim(pt_m, ptsec, "ptbl")

    ndirs = nfiles = nassoc = 0
    iso_files = {}
    iso_file_bytes = 0
    for e in entries:
        n = (e["size"] + SECTOR - 1) // SECTOR
        full = e["path"] + e["name"]
        if e["isdir"]:
            claim(e["extent"], max(n, 1), "isodir")
            ndirs += 1
        else:
            claim(e["extent"], n, "isofile")
            nfiles += 1
            iso_file_bytes += e["size"]
            assoc = bool(e["flags"] & 0x04)
            if assoc:
                nassoc += 1
            iso_files[(full, assoc)] = (e["extent"], e["size"])

    # ---------------------------------------------------------------- HFS side
    src = hfs.Source(image=a.image)
    part, pm = hfs.find_hfs(src)
    vol = hfs.Volume(src, part)
    m = vol.mdb
    ablk = m["drAlBlkSiz"]
    per_ab = ablk // SECTOR
    vol_byte = vol.vol_byte

    claim(vol_byte // SECTOR, 1, "hfsvol")              # boot blocks + MDB
    bm_byte = vol_byte + m["drVBMSt"] * 512
    bm_bytes = (m["drNmAlBlks"] + 7) // 8
    claim(bm_byte // SECTOR,
          ((bm_byte % SECTOR) + bm_bytes + SECTOR - 1) // SECTOR, "hfsvol")
    alt = vol_byte + (part["size"] - 2) * 512
    claim(alt // SECTOR, 1, "hfsvol")

    def claim_ab(extrec, cls):
        for start, count in extrec:
            if count == 0:
                continue
            b = vol.alloc_byte(start)
            assert b % SECTOR == 0, "allocation block not sector aligned"
            claim(b // SECTOR, count * per_ab, cls)

    claim_ab(m["drCTExtRec"], "hfsbt")
    claim_ab(m["drXTExtRec"], "hfsbt")

    hdr, recs = hfs.parse_catalog(vol.catalog())
    dirs, path_of = hfs.build_paths(recs)
    hfs_files = {}
    hfs_data_bytes = hfs_rsrc_bytes = 0
    n_rsrc = 0
    three_ext = 0
    for r in recs:
        if r["type"] != "file":
            continue
        f = hfs.filrec(r["data"])
        p = hfs.escname(path_of(r["parent"]) + "/" + r["name"])
        hfs_files[p] = f
        claim_ab(f["data_extents"], "hfsfile")
        claim_ab(f["rsrc_extents"], "hfsfile")
        hfs_data_bytes += f["data_len"]
        hfs_rsrc_bytes += f["rsrc_len"]
        if f["rsrc_len"]:
            n_rsrc += 1
        if all(e[1] for e in f["data_extents"]):
            three_ext += 1

    # ------------------------------------------------------------- accounting
    per_class = collections.Counter()
    nown = collections.Counter()
    combos = collections.Counter()
    for o in owners:
        u = tuple(sorted(set(o)))
        nown[len(u)] += 1
        combos[u] += 1
        for c in u:
            per_class[c] += 1

    unowned = [s for s in range(volspace) if not owners[s]]

    print("image                %d bytes = %d sectors" % (size, total_img))
    print("volume space         %d sectors = %d bytes"
          % (volspace, volspace * SECTOR))
    print("image tail           %d sectors beyond the volume space"
          % (total_img - volspace))
    print()
    print("ISO   %d directories, %d file records (%d Associated), %d bytes"
          % (ndirs, nfiles, nassoc, iso_file_bytes))
    print("HFS   %d files, %d with a resource fork; data %d B, rsrc %d B"
          % (len(hfs_files), n_rsrc, hfs_data_bytes, hfs_rsrc_bytes))
    print("      allocation block %d bytes = %d sectors; %d alloc blocks, %d free"
          % (ablk, per_ab, m["drNmAlBlks"], m["drFreeBks"]))
    print("      forks using all three extent slots: %d" % three_ext)
    print()
    print("sectors by number of DISTINCT owner classes:")
    for k in sorted(nown):
        print("  %d  %8d  %8.4f %%" % (k, nown[k], 100.0 * nown[k] / volspace))
    print()
    print("sectors per class (a sector may be in several):")
    for c, n in sorted(per_class.items(), key=lambda kv: -kv[1]):
        print("  %-9s %8d  %8.4f %%  = %d bytes"
              % (c, n, 100.0 * n / volspace, n * SECTOR))
    print()
    print("the ten commonest ownership combinations:")
    for u, n in combos.most_common(10):
        print("  %-34s %8d  %8.4f %%"
              % ("+".join(u) if u else "(nobody)", n, 100.0 * n / volspace))
    print()
    print("unowned by EITHER catalogue: %d sectors = %d bytes = %.4f %%"
          % (len(unowned), len(unowned) * SECTOR,
             100.0 * len(unowned) / volspace))
    iso_only_unowned = [s for s in range(volspace)
                        if not any(c in ("sys", "vd", "ptbl", "isodir",
                                         "isofile") for c in owners[s])]
    print("unowned by the ISO catalogue alone: %d sectors = %d bytes = %.4f %%"
          % (len(iso_only_unowned), len(iso_only_unowned) * SECTOR,
             100.0 * len(iso_only_unowned) / volspace))

    if a.align:
        # Does every ISO file extent start on an HFS allocation-block boundary?
        base = vol.alloc_byte(0) // SECTOR
        ok = bad = 0
        offs = collections.Counter()
        for (full, assoc), (ext, sz) in iso_files.items():
            d = (ext - base) % per_ab
            offs[d] += 1
            if d == 0:
                ok += 1
            else:
                bad += 1
        print()
        print("alignment of ISO file extents to the %d-sector HFS grid"
              % per_ab)
        print("  first allocation block at LBA %d" % base)
        for d in sorted(offs):
            print("    offset %d : %6d records  %7.4f %%"
                  % (d, offs[d], 100.0 * offs[d] / nfiles))
        print("  on the grid %d of %d = %.4f %%"
              % (ok, nfiles, 100.0 * ok / nfiles))

    if a.unowned or a.dump_unowned:
        runs = []
        for s in unowned:
            if runs and runs[-1][0] + runs[-1][1] == s:
                runs[-1][1] += 1
            else:
                runs.append([s, 1])
        print()
        print("unowned runs: %d" % len(runs))
        hist = collections.Counter(r[1] for r in runs)
        for ln in sorted(hist):
            print("  run length %5d sectors  x %6d  = %8d sectors"
                  % (ln, hist[ln], ln * hist[ln]))
        if a.dump_unowned:
            with open(a.dump_unowned, "w") as fo:
                for s, n in runs:
                    fo.write("%d\t%d\n" % (s, n))
            print("wrote %s" % a.dump_unowned)

    if a.only_hfs or a.only_iso:
        # Names cannot be matched directly: the ISO side is ISO 9660 level 1,
        # eight-plus-three and upper case, while the HFS side carries the real
        # 31-character Macintosh names. Toast truncated one from the other and
        # the mapping is not recoverable from the strings. The two catalogues
        # do agree on ONE thing that cannot be truncated -- where the bytes
        # are -- so files are matched by the LBA of their first extent.
        base = vol.alloc_byte(0) // SECTOR
        iso_by_lba = {}
        for (full, assoc), (ext, sz) in iso_files.items():
            iso_by_lba.setdefault(ext, []).append((full, sz, assoc))
        hfs_by_lba = {}
        for p, f in hfs_files.items():
            for start, count in f["data_extents"]:
                if count:
                    hfs_by_lba.setdefault(vol.alloc_byte(start) // SECTOR,
                                          []).append((p, f, "data"))
                    break
            for start, count in f["rsrc_extents"]:
                if count:
                    hfs_by_lba.setdefault(vol.alloc_byte(start) // SECTOR,
                                          []).append((p, f, "rsrc"))
                    break
        if a.only_hfs:
            print()
            print("HFS forks whose LBA no ISO record points at:")
            n = 0
            for lba in sorted(hfs_by_lba):
                if lba not in iso_by_lba:
                    for p, f, which in hfs_by_lba[lba]:
                        n += 1
                        print("  LBA %8d  %-42s %s %9d B  type %r creator %r"
                              % (lba, p, which,
                                 f["data_len"] if which == "data" else f["rsrc_len"],
                                 f["type"], f["creator"]))
            print("  total: %d" % n)
        if a.only_iso:
            print()
            print("ISO records whose LBA no HFS fork points at:")
            n = 0
            for lba in sorted(iso_by_lba):
                if lba not in hfs_by_lba:
                    for full, sz, assoc in iso_by_lba[lba]:
                        n += 1
                        print("  LBA %8d  %-42s %9d B%s"
                              % (lba, full, sz, "  (Associated)" if assoc else ""))
            print("  total: %d" % n)
        print()
        print("LBAs in both catalogues: %d ; ISO records %d ; HFS forks %d"
              % (len(set(iso_by_lba) & set(hfs_by_lba)),
                 sum(len(v) for v in iso_by_lba.values()),
                 sum(len(v) for v in hfs_by_lba.values())))

    if False:
        def isokey(full):
            p = full.lstrip("/")
            if p.endswith(";1"):
                p = p[:-2]
            return p.upper().replace("/", "\\")

        def hfskey(p):
            p = p.split("/", 1)[1] if "/" in p else p
            return p.upper().replace("/", "\\")

        iso_set = {}
        for (full, assoc), v in iso_files.items():
            if not assoc:
                iso_set[isokey(full)] = v
        hfs_set = {hfskey(p): p for p in hfs_files}
        if a.only_hfs:
            print()
            print("in the HFS catalogue and NOT in the ISO tree:")
            for k in sorted(hfs_set):
                if k not in iso_set:
                    p = hfs_set[k]
                    f = hfs_files[p]
                    print("  %-46s data %9d  rsrc %8d  type %r creator %r"
                          % (p, f["data_len"], f["rsrc_len"],
                             f["type"], f["creator"]))
        if a.only_iso:
            print()
            print("in the ISO tree and NOT in the HFS catalogue:")
            for k in sorted(iso_set):
                if k not in hfs_set:
                    print("  %-46s %d bytes" % (k, iso_set[k][1]))

    print()
    assert len(unowned) + (volspace - len(unowned)) == volspace
    print("owned %d + unowned %d = %d = volume space  OK"
          % (volspace - len(unowned), len(unowned), volspace))


if __name__ == "__main__":
    main()
