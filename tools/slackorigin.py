#!/usr/bin/env python3
"""slackorigin.py -- where does the padding come from?

`slack.py` establishes that 6,763 sectors of this volume sit between the end of
a file's ISO extent and the end of its HFS allocation block, and that every one
of them is non-zero. Non-zero padding has exactly three possible origins and
they are distinguishable:

  1. the tail of the file it follows, written twice -- tested by slack.py
     and refuted, 0 of 2,395;
  2. bytes of some OTHER file that IS on this disc, left in the mastering
     program's buffer;
  3. bytes that are on no file of this disc at all, i.e. residue of the
     source volume that made the master.

This tool takes a sample of slack regions, extracts a probe of `--probe` bytes
from each, and searches the whole image for that probe outside the region it
came from. A hit inside a file extent is case 2. No hit anywhere is case 3.

The search is `mmap.find`, which is a memchr loop in C over 509 MB; a probe of
32 bytes over a sample of 40 regions is a few seconds. This samples rather than
censuses, and says so on the line that prints the number.

    python tools/slackorigin.py IMAGE --sample 40
    python tools/slackorigin.py IMAGE --sample 40 --probe 64
"""
import argparse
import bisect
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import iso9660

SECTOR = 2048


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("image")
    ap.add_argument("--sample", type=int, default=40)
    ap.add_argument("--probe", type=int, default=32)
    ap.add_argument("--ablk", type=int, default=10240)
    a = ap.parse_args()

    fh, mm = iso9660.open_image(a.image)
    entries = iso9660.tree_of(mm, iso9660.read_vds(mm), False)

    files = []
    for e in entries:
        if e["isdir"]:
            continue
        files.append((e["extent"], e["size"], e["path"] + e["name"]))
    files.sort()
    starts = [f[0] for f in files]

    def owner_of(byte):
        """Which ISO file extent, if any, covers this byte offset."""
        lba = byte // SECTOR
        i = bisect.bisect_right(starts, lba) - 1
        while i >= 0:
            ext, sz, path = files[i]
            if ext + (sz + SECTOR - 1) // SECTOR > lba:
                return path, byte - ext * SECTOR
            i -= 1
        return None, None

    regions = []
    for ext, sz, path in files:
        i = (sz + SECTOR - 1) // SECTOR
        h = ((sz + a.ablk - 1) // a.ablk) * (a.ablk // SECTOR)
        if h > i:
            regions.append((ext + i, h - i, path, sz))

    step = max(1, len(regions) // a.sample)
    sample = regions[::step][:a.sample]

    print("slack regions total   %d" % len(regions))
    print("sampled               %d of %d  (every %dth)"
          % (len(sample), len(regions), step))
    print("probe                 %d bytes" % a.probe)
    print()

    same_file = other_file = nowhere = degenerate = absent = 0
    hits = []
    for lba, n, path, sz in sample:
        base = lba * SECTOR
        blob = mm[base:base + n * SECTOR]
        # take the probe from the middle, away from any zero run at the edges
        mid = len(blob) // 2
        probe = bytes(blob[mid:mid + a.probe])
        if len(set(probe)) < 4:
            degenerate += 1
            continue
        found = []
        pos = mm.find(probe, 0)
        while pos != -1 and len(found) < 6:
            if not (base <= pos < base + n * SECTOR):
                found.append(pos)
            pos = mm.find(probe, pos + 1)
        if not found:
            absent += 1
            hits.append((path, lba, n, "(absent from the image)", None))
            continue
        owner, off = owner_of(found[0])
        if owner == path:
            same_file += 1
        elif owner is None:
            nowhere += 1
            hits.append((path, lba, n, "(in the image, but in no file)", None))
            continue
        else:
            other_file += 1
        hits.append((path, lba, n, owner, off))

    print("of %d probes:" % (len(sample) - degenerate))
    print("  found inside the SAME file's extent    %d" % same_file)
    print("  found inside ANOTHER file's extent     %d" % other_file)
    print("  in the image but inside NO file extent %d" % nowhere)
    print("  absent from the image entirely         %d" % absent)
    print("  probe too uniform to search            %d" % degenerate)
    print()
    print("first 25 results:")
    for path, lba, n, owner, off in hits[:25]:
        if off is None:
            print("  slack after %-44s LBA %7d +%d -> %s"
                  % (path[:44], lba, n, owner))
        else:
            print("  slack after %-44s LBA %7d +%d -> %s + %d"
                  % (path[:44], lba, n, owner, off))


if __name__ == "__main__":
    main()
