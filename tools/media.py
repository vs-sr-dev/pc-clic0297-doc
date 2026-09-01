#!/usr/bin/env python3
"""media.py -- every picture, sound and film on the disc, from its own header.

Eight inherited tools census one media format each and all of them assume the
disc has one. This one walks the tree once and reads whichever header each file
actually has: JPEG SOF, GIF screen descriptor, BMP header, RIFF/AVI stream
headers, RIFF/WAVE fmt, AIFF COMM, QuickTime stsd. Nothing is decoded; every
number is a field.

The point on a compilation disc is not the totals but the *spread*: how many
different codecs, how many different sampling rates, how many different tools
left their signature. A single production uses one encoder; an archive uses
whatever each contributor had.

    python tools/media.py _work/iso _work/hfs
    python tools/media.py _work/iso --tsv notes/media.tsv
"""
import argparse
import os
import struct
from collections import Counter


def jpeg(d):
    off = 2
    w = h = 0
    prec = 0
    comps = 0
    prog = False
    while off + 4 <= len(d):
        if d[off] != 0xFF:
            break
        mk = d[off + 1]
        if mk in (0xD8, 0x01) or 0xD0 <= mk <= 0xD7:
            off += 2
            continue
        ln = struct.unpack(">H", d[off + 2:off + 4])[0]
        if 0xC0 <= mk <= 0xCF and mk not in (0xC4, 0xC8, 0xCC):
            prec = d[off + 4]
            h, w = struct.unpack(">HH", d[off + 5:off + 9])
            comps = d[off + 9]
            prog = mk in (0xC2, 0xC6, 0xCA)
            break
        if mk == 0xDA:
            break
        off += 2 + ln
    return "JPEG", "%dx%d, %d comp, %d bit%s" % (
        w, h, comps, prec, ", progressive" if prog else "")


def gif(d):
    w, h = struct.unpack("<HH", d[6:10])
    flags = d[10]
    ncol = 2 << (flags & 7) if flags & 0x80 else 0
    frames = d.count(b"\x00\x21\xf9\x04") or d.count(b"\x21\xf9\x04")
    return "GIF", "%s, %dx%d, %d colours, %d graphic-control blocks" % (
        d[3:6].decode("latin-1"), w, h, ncol, frames)


def bmp(d):
    w, h = struct.unpack("<ii", d[18:26])
    bits = struct.unpack("<H", d[28:30])[0]
    return "BMP", "%dx%d, %d bpp" % (w, h, bits)


def riff(d):
    form = d[8:12]
    off = 12
    bits = []
    codecs = []
    while off + 8 <= len(d):
        ck = d[off:off + 4]
        ln = struct.unpack("<I", d[off + 4:off + 8])[0]
        if ck == b"LIST":
            sub = d[off + 12:off + 16] if off + 16 <= len(d) else b""
            off += 12
            continue
        if ck == b"avih" and off + 8 + 56 <= len(d):
            us, mb, pad, fl, tot, init, streams, bufsz, w, h = struct.unpack(
                "<IIIIIIIII I".replace(" ", ""), d[off + 8:off + 8 + 40])
            bits.append("%dx%d, %d frames, %.1f fps, %d streams"
                        % (w, h, tot, 1e6 / us if us else 0, streams))
        if ck == b"strf" and off + 8 + 20 <= len(d):
            fcc = d[off + 8 + 16:off + 8 + 20]
            if fcc.strip(b"\x00"):
                codecs.append(fcc.decode("latin-1", "replace"))
        if ck == b"fmt " and off + 8 + 16 <= len(d):
            tag, ch, rate, bps, align, bits_ = struct.unpack(
                "<HHIIHH", d[off + 8:off + 8 + 16])
            bits.append("format 0x%04x, %d ch, %d Hz, %d bit"
                        % (tag, ch, rate, bits_))
        off += 8 + ln + (ln & 1)
    if codecs:
        bits.append("codec " + "+".join(sorted(set(codecs))))
    return "RIFF/" + form.decode("latin-1").strip(), "; ".join(bits)


def aiff(d):
    off = 12
    bits = []
    while off + 8 <= len(d):
        ck = d[off:off + 4]
        ln = struct.unpack(">I", d[off + 4:off + 8])[0]
        if ck == b"COMM" and off + 8 + 18 <= len(d):
            ch, nf = struct.unpack(">HI", d[off + 8:off + 14])
            sz = struct.unpack(">H", d[off + 14:off + 16])[0]
            e = struct.unpack(">H", d[off + 16:off + 18])[0]
            m = struct.unpack(">Q", d[off + 18:off + 26])[0]
            rate = 0
            if e:
                rate = m * (2.0 ** (e - 16383 - 63))
            bits.append("%d ch, %d frames, %d bit, %.0f Hz, %.2f s"
                        % (ch, nf, sz, rate, nf / rate if rate else 0))
            if ln >= 22 and off + 8 + 22 <= len(d):
                bits.append("codec %r"
                            % d[off + 26:off + 30].decode("latin-1", "replace"))
        off += 8 + ln + (ln & 1)
    return d[8:12].decode("latin-1"), "; ".join(bits)


def mov(d):
    codecs = []
    i = 0
    while True:
        i = d.find(b"stsd", i)
        if i < 0:
            break
        n = struct.unpack(">I", d[i + 8:i + 12])[0] if i + 12 <= len(d) else 0
        p = i + 12
        for _ in range(min(n, 8)):
            if p + 12 > len(d):
                break
            sz = struct.unpack(">I", d[p:p + 4])[0]
            codecs.append(d[p + 4:p + 8].decode("latin-1", "replace"))
            if sz < 8:
                break
            p += sz
        i += 4
    dur = ""
    j = d.find(b"mvhd")
    if j > 0 and j + 24 <= len(d):
        ts, du = struct.unpack(">II", d[j + 16:j + 24])
        if ts:
            dur = "%.1f s, " % (du / ts)
    return "MooV", "%scodecs %s" % (dur, "+".join(sorted(set(codecs))) or "none")


def midi(d):
    fmt, ntrk, div = struct.unpack(">HHH", d[8:14])
    return "MIDI", "format %d, %d tracks, division %d" % (fmt, ntrk, div)


def classify(p):
    with open(p, "rb") as fh:
        d = fh.read()
    if len(d) < 16:
        return None
    if d[:2] == b"\xff\xd8":
        return jpeg(d)
    if d[:3] == b"GIF":
        return gif(d)
    if d[:2] == b"BM" and len(d) > 30:
        return bmp(d)
    if d[:4] in (b"RIFF", b"RIFX"):
        return riff(d)
    if d[:4] == b"FORM" and d[8:12] in (b"AIFF", b"AIFC"):
        return aiff(d)
    if d[:4] == b"MThd":
        return midi(d)
    if d[4:8] in (b"moov", b"mdat", b"ftyp", b"wide", b"free", b"skip", b"pnot"):
        return mov(d)
    return None


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("roots", nargs="+")
    ap.add_argument("--tsv")
    ap.add_argument("--list", action="store_true")
    a = ap.parse_args()

    rows = []
    for root in a.roots:
        for dp, dn, fn in os.walk(root):
            for f in sorted(fn):
                p = os.path.join(dp, f)
                try:
                    r = classify(p)
                except Exception as e:
                    r = ("(probe failed)", e.__class__.__name__)
                if r:
                    rows.append((root, os.path.relpath(p, root)
                                 .replace(os.sep, "/"),
                                 os.path.getsize(p), r[0], r[1]))

    print("media files found : %d" % len(rows))
    print("bytes             : %d" % sum(r[2] for r in rows))
    print()
    k = Counter(r[3] for r in rows)
    kb = Counter()
    for r in rows:
        kb[r[3]] += r[2]
    print("%-12s %6s %14s" % ("kind", "files", "bytes"))
    for kk, n in k.most_common():
        print("%-12s %6d %14d" % (kk, n, kb[kk]))
    print()

    for label, needle in (("video codecs (AVI strf / QuickTime stsd)", "codec"),
                          ("audio formats (WAVE fmt)", "format 0x")):
        c = Counter()
        for r in rows:
            for piece in r[4].split("; "):
                if piece.startswith(needle):
                    c[piece] += 1
        if c:
            print("%s:" % label)
            for s, n in c.most_common(20):
                print("   %-46s %4d" % (s, n))
            print()

    print("JPEG geometry, distinct sizes:")
    c = Counter(r[4].split(",")[0] for r in rows if r[3] == "JPEG")
    for s, n in c.most_common(12):
        print("   %-16s %4d" % (s, n))
    print()
    print("AIFF sampling rates:")
    c = Counter()
    for r in rows:
        if r[3].startswith("AIF"):
            for piece in r[4].split(", "):
                if piece.endswith("Hz"):
                    c[piece] += 1
    for s, n in c.most_common():
        print("   %-16s %4d" % (s, n))

    if a.list:
        print()
        for r in sorted(rows):
            print("%-8s %-50s %10d %-10s %s"
                  % (r[0].split("/")[-1], r[1][:50], r[2], r[3], r[4]))

    if a.tsv:
        with open(a.tsv, "w", encoding="utf-8", newline="") as fh:
            fh.write("root\tpath\tsize\tkind\tdetail\n")
            for r in rows:
                fh.write("%s\t%s\t%d\t%s\t%s\n" % r)
        print()
        print("wrote %s" % a.tsv)


if __name__ == "__main__":
    main()
