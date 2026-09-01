#!/usr/bin/env python3
"""swa.py -- Shockwave Audio headers, and 517 files turned into minutes.

The commercial blurb for this title promises "oltre 40 minuti di musiche
originali". The disc carries 517 `.swa` files totalling 175,045,857 bytes. Those
two facts cannot both be about the same set of bytes at any bitrate a 2000 CD
would use, and this tool exists to say by how much rather than to guess.

A Shockwave Audio file is an MPEG audio stream behind a Macromedia header. The
header is **big-endian**, like everything else this title's Macintosh authoring
produced, and its length is its own first field, so the audio starts at a
position the file declares rather than one a scanner has to find.

    python tools/swa.py _work/iso/MAudio
    python tools/swa.py _work/iso/MAudio --tsv notes/swa.tsv
    python tools/swa.py _work/iso/MAudio/001_001.swa --header

THE HEADER, ASSERTED
--------------------
    0   4  header length, in bytes, from the start of the file
    4   4  a version-like field: 3 on every file here
    8   4  sample rate in Hz
   12   4  bit rate in bits per second
   16   4  a constant this disc does not vary: 1393 on all 517
   20   4  sample count
   24   8  0xFF filler
   32   4  a pair of small integers
   36   4  'MACR', the Macromedia creator code
   40  16  a 16-byte identifier, constant across the disc
   56   8  zero
   64   n  the copyright string

Everything after the copyright string and before the declared header length is
**not initialised**, and that is a finding rather than a nuisance: see
`--garbage`.

TWO INDEPENDENT DURATIONS
-------------------------
The header gives a sample count and a sample rate, so duration = samples / rate.
The file also has a length and a bit rate, so duration = (size - header) * 8 /
bitrate. The two are computed from disjoint fields and the tool prints both and
their difference. A file where they disagree by more than a frame is a file
whose header does not describe its body.
"""
import argparse
import os
import struct
import sys

MPEG_BITRATE_V1L3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224,
                     256, 320, 0]
# MPEG-2 and MPEG-2.5 Layer III have their own, lower, bitrate table. 25 of the
# 517 files on this disc are MPEG-2 -- every file whose header declares 22,050
# or 16,000 Hz, which are rates MPEG-1 cannot express. A reader that accepts
# only MPEG-1 rejects exactly those 25 and then reports a frame count that is
# short by precisely the interesting files.
MPEG_BITRATE_V2L3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144,
                     160, 0]
MPEG_RATE = {3: [44100, 48000, 32000, 0],    # MPEG-1
             2: [22050, 24000, 16000, 0],    # MPEG-2
             0: [11025, 12000, 8000, 0]}     # MPEG-2.5
MPEG_NAME = {3: "MPEG-1", 2: "MPEG-2", 0: "MPEG-2.5"}
MODES = ["stereo", "joint stereo", "dual channel", "mono"]


def parse_header(b):
    if len(b) < 68:
        return None
    (hlen, ver, rate, brate, k, samples) = struct.unpack(">IIIIII", b[0:24])
    if hlen < 64 or hlen > 65536 or rate not in (8000, 11025, 16000, 22050,
                                                 24000, 32000, 44100, 48000):
        return None
    creator = b[36:40]
    ident = b[40:56]
    # the copyright string runs to its NUL
    end = b.find(b"\0", 64)
    cop = b[64:end if end > 0 else 64]
    return {"header_len": hlen, "version": ver, "rate": rate, "bitrate": brate,
            "const": k, "samples": samples, "creator": creator,
            "ident": ident, "copyright": cop.decode("latin-1")}


def first_frame(b, off):
    """Decode the first MPEG audio frame header at or after `off`."""
    for i in range(off, min(off + 4096, len(b) - 4)):
        if b[i] != 0xFF or (b[i + 1] & 0xE0) != 0xE0:
            continue
        h = b[i:i + 4]
        ver = (h[1] >> 3) & 3      # 3 = MPEG1
        layer = (h[1] >> 1) & 3    # 1 = Layer III
        crc = not (h[1] & 1)
        bi = (h[2] >> 4) & 0xF
        fi = (h[2] >> 2) & 3
        pad = (h[2] >> 1) & 1
        mode = (h[3] >> 6) & 3
        if ver == 1 or layer != 1 or bi in (0, 15) or fi == 3:
            continue
        table = MPEG_BITRATE_V1L3 if ver == 3 else MPEG_BITRATE_V2L3
        return {"at": i, "mpeg": MPEG_NAME[ver], "layer": 3, "crc": crc,
                "bitrate": table[bi] * 1000,
                "rate": MPEG_RATE[ver][fi], "padding": pad,
                "mode": MODES[mode], "channels": 1 if mode == 3 else 2}
    return None


def hms(sec):
    s = int(round(sec))
    return "%d:%02d:%02d" % (s // 3600, (s % 3600) // 60, s % 60)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--tsv")
    ap.add_argument("--header", action="store_true")
    ap.add_argument("--garbage", action="store_true",
                    help="report the uninitialised tail of each header")
    a = ap.parse_args()

    files = []
    if os.path.isdir(a.path):
        for dp, dn, fn in os.walk(a.path):
            for n in fn:
                if n.lower().endswith(".swa"):
                    files.append(os.path.join(dp, n))
    else:
        files = [a.path]
    files.sort()

    rows = []
    nohdr = []
    for p in files:
        b = open(p, "rb").read()
        h = parse_header(b)
        if h is None:
            nohdr.append(p)
            continue
        f = first_frame(b, h["header_len"])
        h["path"] = p
        h["size"] = len(b)
        h["frame"] = f
        h["d_samples"] = h["samples"] / float(h["rate"]) if h["rate"] else 0
        payload = len(b) - h["header_len"]
        h["d_bytes"] = payload * 8.0 / h["bitrate"] if h["bitrate"] else 0
        rows.append(h)

    if a.header and rows:
        h = rows[0]
        b = open(h["path"], "rb").read()
        print("file           : %s   %d bytes" % (h["path"], h["size"]))
        print("header length  : %d  (audio begins there)" % h["header_len"])
        print("version field  : %d" % h["version"])
        print("sample rate    : %d Hz" % h["rate"])
        print("bit rate       : %d bit/s" % h["bitrate"])
        print("constant at +16: %d" % h["const"])
        print("sample count   : %d" % h["samples"])
        print("creator        : %r" % h["creator"])
        print("identifier     : %s" % " ".join("%02x" % c for c in h["ident"]))
        print("copyright      : %r" % h["copyright"])
        if h["frame"]:
            f = h["frame"]
            print()
            print("first MPEG frame at offset %d" % f["at"])
            print("  %s Layer %s, %s, %d Hz, %d bit/s, %s"
                  % (f["mpeg"], "III", f["mode"], f["rate"], f["bitrate"],
                     "CRC" if f["crc"] else "no CRC"))
            print("  the frame agrees with the header about the rate: %s"
                  % (f["rate"] == h["rate"]))
            print("  the frame agrees with the header about the bitrate: %s"
                  % (f["bitrate"] == h["bitrate"]))
        print()
        print("duration from samples/rate      : %.3f s" % h["d_samples"])
        print("duration from (size-header)*8/br: %.3f s" % h["d_bytes"])
        print("difference                      : %.3f s"
              % (h["d_bytes"] - h["d_samples"]))
        return

    print("files with a .swa extension : %d" % len(files))
    print("files with a readable header: %d" % len(rows))
    if nohdr:
        print("files whose header did not parse: %d" % len(nohdr))
        for p in nohdr[:10]:
            print("    %s" % p)
    print()

    def census(key, fmt="%s"):
        d = {}
        for r in rows:
            d[r[key]] = d.get(r[key], 0) + 1
        return dict(sorted(d.items()))

    print("sample rate   : %s" % census("rate"))
    print("bit rate      : %s" % census("bitrate"))
    print("version field : %s" % census("version"))
    print("constant +16  : %s" % census("const"))
    print("creator       : %s" % {k.decode("latin-1"): v for k, v in
                                  sorted(census("creator").items())})
    cops = {}
    for r in rows:
        cops[r["copyright"]] = cops.get(r["copyright"], 0) + 1
    print("copyright     : %s" % cops)
    idents = {}
    for r in rows:
        idents[bytes(r["ident"])] = idents.get(bytes(r["ident"]), 0) + 1
    print("identifiers   : %d distinct" % len(idents))
    for k, v in sorted(idents.items(), key=lambda x: -x[1])[:4]:
        print("    %s   %d files" % (" ".join("%02x" % c for c in k), v))
    print()

    modes = {}
    disagree_rate = disagree_br = 0
    noframe = 0
    for r in rows:
        f = r["frame"]
        if not f:
            noframe += 1
            continue
        modes[f["mode"]] = modes.get(f["mode"], 0) + 1
        if f["rate"] != r["rate"]:
            disagree_rate += 1
        if f["bitrate"] != r["bitrate"]:
            disagree_br += 1
    print("first MPEG frame found after the declared header end : %d of %d"
          % (len(rows) - noframe, len(rows)))
    delta = {}
    for r in rows:
        if r["frame"]:
            d = r["frame"]["at"] - r["header_len"]
            delta[d] = delta.get(d, 0) + 1
    print("gap between the declared header length and the first frame : %s"
          % dict(sorted(delta.items())))
    print("channel mode  : %s" % modes)
    mpegs = {}
    for r in rows:
        if r["frame"]:
            mpegs[r["frame"]["mpeg"]] = mpegs.get(r["frame"]["mpeg"], 0) + 1
    print("MPEG version  : %s" % dict(sorted(mpegs.items())))
    print("frames disagreeing with the header about the sample rate : %d"
          % disagree_rate)
    print("frames disagreeing with the header about the bit rate    : %d"
          % disagree_br)
    print()

    ts = sum(r["d_samples"] for r in rows)
    tb = sum(r["d_bytes"] for r in rows)
    tot = sum(r["size"] for r in rows)
    hdr = sum(r["header_len"] for r in rows)
    print("total bytes                 : %d" % tot)
    print("total header bytes          : %d  (%.4f %% of the files)"
          % (hdr, 100.0 * hdr / tot))
    print()
    print("total duration, from sample counts : %10.1f s = %s" % (ts, hms(ts)))
    print("total duration, from sizes         : %10.1f s = %s" % (tb, hms(tb)))
    print("the two differ by                  : %10.1f s (%.3f %%)"
          % (tb - ts, 100.0 * (tb - ts) / ts if ts else 0))
    print()
    worst = max(rows, key=lambda r: abs(r["d_bytes"] - r["d_samples"]))
    print("largest single-file disagreement   : %.3f s in %s"
          % (worst["d_bytes"] - worst["d_samples"], worst["path"]))
    print()
    print("shortest : %8.2f s  %s" % (min(r["d_samples"] for r in rows),
                                      min(rows, key=lambda r: r["d_samples"])["path"]))
    print("longest  : %8.2f s  %s" % (max(r["d_samples"] for r in rows),
                                      max(rows, key=lambda r: r["d_samples"])["path"]))
    print("mean     : %8.2f s" % (ts / len(rows)))

    if a.garbage:
        print()
        print("--- the uninitialised tail of the header ---")
        print("Everything between the copyright string and the declared header")
        print("length is left as whatever was in memory. Counting how much of")
        print("it is non-zero says whether that is padding or a leak.")
        nz = tot_tail = 0
        allzero = 0
        for r in rows:
            b = open(r["path"], "rb").read(r["header_len"])
            end = b.find(b"\0", 64)
            tail = b[end + 1:] if end > 0 else b[64:]
            tot_tail += len(tail)
            n = sum(1 for c in tail if c)
            nz += n
            if n == 0:
                allzero += 1
        print("bytes after the copyright string : %d" % tot_tail)
        print("of which non-zero                : %d  (%.2f %%)"
              % (nz, 100.0 * nz / tot_tail if tot_tail else 0))
        print("files whose tail is all zero     : %d of %d" % (allzero, len(rows)))

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8") as f:
            f.write("path\tsize\theader_len\trate\tbitrate\tsamples\t"
                    "seconds_samples\tseconds_bytes\tmode\n")
            for r in rows:
                f.write("%s\t%d\t%d\t%d\t%d\t%d\t%.4f\t%.4f\t%s\n"
                        % (r["path"].replace(os.sep, "/"), r["size"],
                           r["header_len"], r["rate"], r["bitrate"],
                           r["samples"], r["d_samples"], r["d_bytes"],
                           r["frame"]["mode"] if r["frame"] else ""))
        print()
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
