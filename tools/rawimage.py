#!/usr/bin/env python3
"""rawimage.py -- one sequential pass over the whole disc, into one file.

Why this exists on this disc and did not exist before. The standing rule in
this collection is "open with a single copy": robocopy the mounted tree and
never touch the drive again. That rule assumes the mounted tree *is* the disc.

On CLIC 11 it is not. The disc carries an Apple partition map and an HFS volume
whose catalogue lists folders Windows never mounts (IE4MAC, PAGMAC, MicroMondi,
"Metti in Cartella Sistema") and 28 files with a resource fork, which no Windows
API will hand over. robocopy copied 857 files and 603 MB; the disc is 661 MB.
The difference is not padding.

So: one linear read of every sector from 0 to the volume space declared in the
primary descriptor, written to a file. Linear reading is the cheapest thing an
optical drive does -- the head does not seek and the cache streams. It is the
single-sector probing with failed reads that kills this drive, and this tool
does none of it unless a big read fails first.

    python tools/rawimage.py E _work/clic11.img --sectors 322926

--chunk defaults to 2048 sectors (4 MiB), well under the 4,096-sector ceiling
this drive was measured to accept. If a chunk read comes back short, and only
then, the tool falls back to single sectors *for that chunk*, records which
sectors failed, and fills them with zeros so that every later address in the
image is still correct. The count of filled sectors is printed at the end and
must be quoted anywhere the image is used.
"""
import argparse
import os
import time

SECTOR = 2048
BS = chr(92)


def devpath(letter):
    return BS + BS + "." + BS + letter.upper().rstrip(":") + ":"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("drive")
    ap.add_argument("out")
    ap.add_argument("--sectors", type=int, required=True)
    ap.add_argument("--chunk", type=int, default=2048)
    a = ap.parse_args()

    fh = open(devpath(a.drive), "rb", buffering=0)
    os.makedirs(os.path.dirname(a.out) or ".", exist_ok=True)
    out = open(a.out, "wb")
    t0 = time.time()
    lba = 0
    bad = []
    while lba < a.sectors:
        n = min(a.chunk, a.sectors - lba)
        try:
            fh.seek(lba * SECTOR)
            d = fh.read(n * SECTOR)
        except OSError:
            d = b""
        if len(d) != n * SECTOR:
            buf = bytearray()
            for i in range(n):
                try:
                    fh.seek((lba + i) * SECTOR)
                    s = fh.read(SECTOR)
                except OSError:
                    s = b""
                if len(s) != SECTOR:
                    s = b"\x00" * SECTOR
                    bad.append(lba + i)
                buf += s
            d = bytes(buf)
        out.write(d)
        lba += n
        if lba % 65536 == 0 or lba == a.sectors:
            el = time.time() - t0
            print("%7d / %d   %8.1f MB   %6.0f s   %.2f MB/s"
                  % (lba, a.sectors, lba * SECTOR / 1048576.0, el,
                     lba * SECTOR / 1048576.0 / max(el, 0.001)), flush=True)
    out.close()
    fh.close()
    el = time.time() - t0
    print()
    print("sectors written : %d" % a.sectors)
    print("bytes written   : %d" % (a.sectors * SECTOR))
    print("sectors filled with zeros after a read failure : %d" % len(bad))
    if bad:
        print("first failures  : %s" % bad[:20])
    print("elapsed         : %.1f s   %.2f MB/s"
          % (el, a.sectors * SECTOR / 1048576.0 / max(el, 0.001)))


if __name__ == "__main__":
    main()
