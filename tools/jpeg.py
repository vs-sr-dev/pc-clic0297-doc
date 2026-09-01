#!/usr/bin/env python3
"""jpeg.py -- read JFIF markers. Dimensions, encoder fingerprints, no decoding.

Two questions on this disc need a JPEG reader and neither of them needs pixels:

  * `PICTURES/JACKET01.00J` is the fourth member of a set whose other three
    members turned out to be MPEG-1 stills at 176x144, 352x288 and 704x576.
    The question is where the JPEG sits in that ladder.
  * `dati/Vrmedia/` holds five large JPEGs that an `.ivr` file next to each one
    declares to be spherical panoramas. A sphere mapped equirectangularly is
    2:1. Measuring the aspect ratio is the difference between believing the
    `.ivr` and checking it.

What it reports, per file:

  * every marker in the stream, in order, with its length -- because the marker
    sequence is itself an encoder fingerprint;
  * SOF type (baseline / extended / progressive / arithmetic), precision,
    dimensions, component count and the per-component sampling factors, which
    give the chroma subsampling;
  * the APP0 JFIF block: version, density units, X and Y density -- 1990s
    stitching software wrote its output density here and it is often the only
    thing distinguishing two otherwise identical files;
  * APP1 (Exif), APP2 (ICC), APP13 (Photoshop IRB) and APP14 (Adobe) presence,
    which say which application last wrote the file;
  * every COM comment, verbatim. Apple's imaging stack writes `AppleMark`
    here and nothing else does, which makes it a platform fingerprint.
  * quantisation and Huffman table counts, and the number of scans.

Markers are walked from SOI using each segment's own length field. Start codes
are never searched for -- entropy-coded scan data contains 0xFF bytes by the
thousand and scanning for markers inside it invents segments. After an SOS the
walker skips entropy data by advancing until it finds an 0xFF followed by a
byte that is neither 0x00 (a stuffed byte) nor an RSTn marker, which is the
only correct way to leave a scan.

    python tools/jpeg.py FILE [FILE...]
    python tools/jpeg.py FILE --markers
    python tools/jpeg.py DIR --recurse
"""
import argparse
import os
import struct
import sys

SOF_NAMES = {
    0xC0: "baseline DCT, Huffman",
    0xC1: "extended sequential DCT, Huffman",
    0xC2: "progressive DCT, Huffman",
    0xC3: "lossless, Huffman",
    0xC5: "differential sequential DCT, Huffman",
    0xC6: "differential progressive DCT, Huffman",
    0xC7: "differential lossless, Huffman",
    0xC9: "extended sequential DCT, arithmetic",
    0xCA: "progressive DCT, arithmetic",
    0xCB: "lossless, arithmetic",
    0xCD: "differential sequential DCT, arithmetic",
    0xCE: "differential progressive DCT, arithmetic",
    0xCF: "differential lossless, arithmetic",
}

MARKER_NAMES = {
    0xD8: "SOI", 0xD9: "EOI", 0xDA: "SOS", 0xDB: "DQT", 0xC4: "DHT",
    0xDD: "DRI", 0xFE: "COM", 0xDC: "DNL",
}
for _i in range(16):
    MARKER_NAMES[0xE0 + _i] = "APP%d" % _i
for _i in range(8):
    MARKER_NAMES[0xD0 + _i] = "RST%d" % _i

DENSITY_UNITS = {0: "aspect ratio only", 1: "pixels per inch", 2: "pixels per cm"}

# Standalone markers carry no length field.
STANDALONE = set([0x01, 0xD8, 0xD9]) | set(range(0xD0, 0xD8))


def walk(data):
    """Yield (offset, marker_byte, payload_bytes_or_None)."""
    if data[0:2] != b"\xFF\xD8":
        raise ValueError("no SOI: file starts %s" % data[0:2].hex())
    pos = 0
    yield 0, 0xD8, None
    pos = 2
    n = len(data)
    while pos < n:
        if data[pos] != 0xFF:
            # Not at a marker. Do not go hunting; report and stop.
            raise ValueError("expected 0xFF at offset %d, found 0x%02X"
                             % (pos, data[pos]))
        m = pos
        while m < n and data[m] == 0xFF:
            m += 1                       # fill bytes are legal before a marker
        if m >= n:
            return
        marker = data[m]
        pos = m + 1
        if marker in STANDALONE:
            yield m - 1, marker, None
            continue
        if pos + 2 > n:
            return
        length = struct.unpack(">H", data[pos:pos + 2])[0]
        payload = data[pos + 2:pos + length]
        yield m - 1, marker, payload
        pos += length
        if marker == 0xDA:
            # Skip entropy-coded data: advance to the next 0xFF that is not
            # followed by 0x00 (byte stuffing) or an RSTn marker.
            while pos < n - 1:
                if data[pos] == 0xFF:
                    nxt = data[pos + 1]
                    if nxt != 0x00 and not (0xD0 <= nxt <= 0xD7):
                        break
                    pos += 2
                else:
                    pos += 1
            else:
                return


def describe(path, show_markers=False):
    data = open(path, "rb").read()
    print("file            : %s" % path)
    print("size            : %d bytes" % len(data))
    if data[0:2] != b"\xFF\xD8":
        print("NOT a JPEG: first bytes %s" % data[0:4].hex(" "))
        return
    order = []
    sof = None
    comments = []
    jfif = None
    apps = {}
    dqt = dht = sos = 0
    try:
        for off, marker, payload in walk(data):
            name = MARKER_NAMES.get(marker, SOF_NAMES.get(marker) and "SOF%d" % (marker - 0xC0) or "0x%02X" % marker)
            if marker in SOF_NAMES:
                name = "SOF%d" % (marker - 0xC0)
            order.append((off, name, marker, 0 if payload is None else len(payload) + 2))
            if marker in SOF_NAMES and sof is None:
                prec = payload[0]
                h, w = struct.unpack(">HH", payload[1:5])
                ncomp = payload[5]
                comps = []
                for i in range(ncomp):
                    cid, hv, tq = payload[6 + i * 3:9 + i * 3]
                    comps.append((cid, hv >> 4, hv & 0x0F, tq))
                sof = (marker, prec, w, h, comps)
            elif marker == 0xFE:
                comments.append(payload)
            elif marker == 0xE0 and payload[:5] == b"JFIF\x00":
                jfif = payload
            elif 0xE0 <= marker <= 0xEF:
                apps.setdefault(name, []).append(payload[:32])
            if marker == 0xDB:
                dqt += 1
            elif marker == 0xC4:
                dht += 1
            elif marker == 0xDA:
                sos += 1
    except ValueError as exc:
        print("marker walk stopped: %s" % exc)

    if sof:
        marker, prec, w, h, comps = sof
        print("SOF             : SOF%d  %s" % (marker - 0xC0, SOF_NAMES[marker]))
        print("dimensions      : %d x %d   (aspect %.4f)" % (w, h, w / h if h else 0))
        print("precision       : %d bits" % prec)
        samp = " ".join("id%d=%dx%d/q%d" % (c[0], c[1], c[2], c[3]) for c in comps)
        print("components      : %d   %s" % (len(comps), samp))
        if len(comps) == 3:
            hmax = max(c[1] for c in comps)
            vmax = max(c[2] for c in comps)
            sub = {(2, 2): "4:2:0", (2, 1): "4:2:2", (1, 1): "4:4:4", (1, 2): "4:4:0"}
            print("subsampling     : %s" % sub.get((hmax, vmax), "%dx%d" % (hmax, vmax)))
    else:
        print("SOF             : none found")

    if jfif:
        ver = "%d.%02d" % (jfif[5], jfif[6])
        unit = jfif[7]
        xd, yd = struct.unpack(">HH", jfif[8:12])
        tw, th = jfif[12], jfif[13]
        print("APP0 JFIF       : version %s, units %d (%s), density %dx%d, thumb %dx%d"
              % (ver, unit, DENSITY_UNITS.get(unit, "?"), xd, yd, tw, th))
    else:
        print("APP0 JFIF       : absent")

    other = [k for k in apps if k != "APP0"]
    print("other APPn      : %s" % (", ".join(sorted(other)) if other else "none"))
    if "APP1" in apps:
        print("    APP1 head   : %r" % apps["APP1"][0][:16])
    if "APP14" in apps:
        print("    APP14 head  : %r" % apps["APP14"][0][:16])

    if comments:
        for c in comments:
            print("COM comment     : %r" % c)
    else:
        print("COM comment     : none")

    print("tables/scans    : DQT %d, DHT %d, SOS %d" % (dqt, dht, sos))
    print("marker sequence : %s" % " ".join(o[1] for o in order))
    if show_markers:
        print()
        print("%-10s %-8s %s" % ("offset", "marker", "segment bytes"))
        for off, name, marker, size in order:
            print("%-10d %-8s %d" % (off, name, size))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--markers", action="store_true")
    ap.add_argument("--recurse", action="store_true")
    args = ap.parse_args()

    files = []
    for p in args.paths:
        if os.path.isdir(p) and args.recurse:
            for dp, dn, fn in os.walk(p):
                dn.sort()
                for f in sorted(fn):
                    if f.lower().endswith((".jpg", ".jpeg", ".jpe")):
                        files.append(os.path.join(dp, f))
        else:
            files.append(p)

    for i, f in enumerate(files):
        if i:
            print()
        describe(f, args.markers)


if __name__ == "__main__":
    main()
