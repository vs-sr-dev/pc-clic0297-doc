#!/usr/bin/env python3
"""audio.py - census the Ogg Vorbis and RIFF WAVE files in a directory tree.

Header reading only, in the manner of mp3.py and avi.py from the previous
two discs: it never decodes a sample. For Ogg it reads the identification
header on the first page, the comment header behind it, and the granule
position on the last page, which is the total sample count and therefore the
exact duration. For WAVE it reads the `fmt ` and `data` chunks and takes the
duration from the byte rate.

Usage:
    python tools/audio.py DIR
    python tools/audio.py DIR --ogg
    python tools/audio.py DIR --wav
    python tools/audio.py DIR --wav --by-dir
"""

import argparse
import os
import struct

WAVE_FORMATS = {1: "PCM", 2: "ADPCM", 6: "A-law", 7: "mu-law",
                0x11: "IMA ADPCM", 0x50: "MPEG", 0x55: "MPEG Layer III",
                0xFFFE: "extensible"}


def walk(root, exts):
    if os.path.isfile(root):
        yield root
        return
    for r, dirs, names in os.walk(root):
        for n in sorted(names):
            e = n.rsplit(".", 1)[-1].lower() if "." in n else ""
            if any(e.startswith(x) for x in exts):
                yield os.path.join(r, n)


# ------------------------------------------------------------------- Ogg
def read_ogg(path):
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:4] != b"OggS":
        return None
    nseg = d[26]
    body = 27 + nseg
    idh = d[body:body + 30]
    if idh[1:7] != b"vorbis" or idh[0] != 1:
        return None
    ver, ch, rate = struct.unpack_from("<IBI", idh, 7)
    bmax, bnom, bmin = struct.unpack_from("<iii", idh, 16)
    bs = idh[28]

    last = d.rfind(b"OggS")
    granule = struct.unpack_from("<q", d, last + 6)[0]

    vendor, comments = "", []
    j = d.find(b"\x03vorbis")
    if j > 0:
        vl = struct.unpack_from("<I", d, j + 7)[0]
        vendor = d[j + 11:j + 11 + vl].decode("utf-8", "replace")
        n = struct.unpack_from("<I", d, j + 11 + vl)[0]
        p = j + 15 + vl
        for _ in range(n):
            L = struct.unpack_from("<I", d, p)[0]
            comments.append(d[p + 4:p + 4 + L].decode("utf-8", "replace"))
            p += 4 + L

    return {"path": path, "bytes": len(d), "version": ver, "channels": ch,
            "rate": rate, "nominal": bnom, "min": bmin, "max": bmax,
            "blocksize0": 1 << (bs & 0x0F), "blocksize1": 1 << (bs >> 4),
            "samples": granule, "seconds": granule / float(rate),
            "vendor": vendor, "comments": comments}


def cmd_ogg(root):
    rows = [r for r in (read_ogg(p) for p in walk(root, ("ogg",))) if r]
    if not rows:
        print("no Ogg Vorbis files")
        return
    print("%-18s %10s %3s %7s %9s %10s %11s"
          % ("file", "bytes", "ch", "Hz", "nominal", "seconds", "actual b/s"))
    tb = ts = 0
    for r in sorted(rows, key=lambda x: -x["bytes"]):
        print("%-18s %10d %3d %7d %9d %10.2f %11.0f"
              % (os.path.basename(r["path"]), r["bytes"], r["channels"],
                 r["rate"], r["nominal"], r["seconds"],
                 r["bytes"] * 8 / r["seconds"]))
        tb += r["bytes"]
        ts += r["seconds"]
    print()
    print("files      %d" % len(rows))
    print("bytes      %d" % tb)
    print("duration   %.2f s = %d min %05.2f s" % (ts, int(ts) // 60, ts % 60))
    print("mean rate  %.0f bit/s" % (tb * 8 / ts))
    print()
    vend = {}
    coms = {}
    blocks = {}
    for r in rows:
        vend[r["vendor"]] = vend.get(r["vendor"], 0) + 1
        for c in r["comments"]:
            coms[c] = coms.get(c, 0) + 1
        k = (r["blocksize0"], r["blocksize1"])
        blocks[k] = blocks.get(k, 0) + 1
    print("-- encoder")
    for v, n in sorted(vend.items(), key=lambda kv: -kv[1]):
        print("   vendor    %-42s x%d" % (repr(v), n))
    for c, n in sorted(coms.items(), key=lambda kv: -kv[1]):
        print("   comment   %-42s x%d" % (repr(c), n))
    for k, n in sorted(blocks.items()):
        print("   blocksize %d / %-34d x%d" % (k[0], k[1], n))


# ------------------------------------------------------------------ WAVE
def read_wav(path):
    with open(path, "rb") as fh:
        d = fh.read()
    if d[:4] != b"RIFF" or d[8:12] != b"WAVE":
        return {"path": path, "bytes": len(d), "bad": True}
    out = {"path": path, "bytes": len(d), "bad": False, "chunks": []}
    i = 12
    byterate = None
    while i + 8 <= len(d):
        cid = d[i:i + 4]
        sz = struct.unpack_from("<I", d, i + 4)[0]
        out["chunks"].append(cid.decode("latin-1"))
        if cid == b"fmt ":
            tag, ch, rate, byterate, align, bits = struct.unpack_from(
                "<HHIIHH", d, i + 8)
            out.update({"tag": tag, "channels": ch, "rate": rate,
                        "byterate": byterate, "align": align, "bits": bits})
        elif cid == b"data":
            out["data"] = sz
            out["seconds"] = sz / float(byterate) if byterate else 0.0
        i += 8 + sz + (sz & 1)
    return out


def cmd_wav(root, by_dir):
    rows = [read_wav(p) for p in walk(root, ("wav",))]
    good = [r for r in rows if not r.get("bad")]
    print("files              %d" % len(rows))
    print("not RIFF/WAVE      %d" % (len(rows) - len(good)))
    print("bytes              %d" % sum(r["bytes"] for r in rows))
    secs = sum(r.get("seconds", 0) for r in good)
    print("duration           %.2f s = %d min %05.2f s"
          % (secs, int(secs) // 60, secs % 60))
    print("mean length        %.3f s" % (secs / len(good) if good else 0))
    print()
    fmts = {}
    chunks = {}
    for r in good:
        k = (WAVE_FORMATS.get(r.get("tag"), r.get("tag")), r.get("channels"),
             r.get("rate"), r.get("bits"))
        fmts[k] = fmts.get(k, 0) + 1
        chunks[tuple(r["chunks"])] = chunks.get(tuple(r["chunks"]), 0) + 1
    print("-- format")
    print("   %-12s %3s %8s %5s   %6s" % ("encoding", "ch", "Hz", "bits", "count"))
    for k, n in sorted(fmts.items(), key=lambda kv: -kv[1]):
        print("   %-12s %3s %8s %5s   %6d" % (k[0], k[1], k[2], k[3], n))
    print()
    print("-- chunk layout")
    for k, n in sorted(chunks.items(), key=lambda kv: -kv[1]):
        print("   %-40s %6d" % (", ".join(k), n))

    if by_dir:
        print()
        print("-- by directory")
        agg = {}
        for r in good:
            dd = os.path.dirname(r["path"])
            c, b, s = agg.get(dd, (0, 0, 0.0))
            agg[dd] = (c + 1, b + r["bytes"], s + r.get("seconds", 0))
        for dd, (c, b, s) in sorted(agg.items(), key=lambda kv: -kv[1][1]):
            print("   %-40s %5d files %10d bytes %8.2f s"
                  % (os.path.basename(dd) or dd, c, b, s))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--ogg", action="store_true")
    ap.add_argument("--wav", action="store_true")
    ap.add_argument("--by-dir", action="store_true")
    a = ap.parse_args()
    if not (a.ogg or a.wav):
        a.ogg = a.wav = True
    if a.ogg:
        print("=" * 72)
        print("OGG VORBIS")
        print("=" * 72)
        cmd_ogg(a.path)
        print()
    if a.wav:
        print("=" * 72)
        print("RIFF WAVE")
        print("=" * 72)
        cmd_wav(a.path, a.by_dir)


if __name__ == "__main__":
    main()
