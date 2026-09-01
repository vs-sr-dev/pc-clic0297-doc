#!/usr/bin/env python3
"""cabsig.py -- what is in a cabinet after the cabinet ends.

cab.py reports, for every one of this disc's 43 cabinets, that the file is
larger than its own cbCabinet field says. The differences take three values --
6,832, 6,848 and 6,920 -- which is the shape of something appended rather than
of corruption. "Obvious reading" is not a measurement, so this parses it.

A cabinet's header carries cbCabinet at +8, and MSCF sets the RESERVE_PRESENT
flag (0x0004) when the header has extra fields. The bytes past cbCabinet are
outside the format.

The answer, measured on all 43: the tail is a **bare DER PKCS#7 SignedData**,
starting 30 82 <len16> and then the signedData OID 1.2.840.113549.1.7.2. There
is **no WIN_CERTIFICATE header** -- that is where a cabinet differs from a PE,
and the first version of this tool, which assumed the PE layout, called all 43
tails "unrecognised". The difference is eight bytes and it is the whole
finding.

    python tools/cabsig.py _work/iso/DirectX/*.cab
    python tools/cabsig.py _work/iso/DirectX/DirectX.cab --names
"""
import argparse
import collections
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--names", action="store_true",
                    help="also pull the names out of the DER, via authenticode.py")
    a = ap.parse_args()

    print("%-34s %10s %10s %8s %-6s %s"
          % ("cabinet", "file size", "cbCabinet", "tail", "type", "tail sha1"))
    sizes = collections.Counter()
    types = collections.Counter()
    blobs = collections.Counter()
    rows = []
    for p in a.paths:
        d = open(p, "rb").read()
        if d[:4] != b"MSCF":
            print("%-34s  not a cabinet" % os.path.basename(p))
            continue
        cb = struct.unpack_from("<I", d, 8)[0]
        tail = d[cb:]
        kind = "-"
        if len(tail) >= 8:
            # A PE appends a WIN_CERTIFICATE header before the PKCS#7 blob.
            # A cabinet does not: the tail begins with the DER directly, so
            # 30 82 <len16>, then the signedData OID 1.2.840.113549.1.7.2,
            # which in DER is 06 09 2a 86 48 86 f7 0d 01 07 02.
            SEQ = bytes((0x30, 0x82))
            OID = bytes((0x06, 0x09, 0x2a, 0x86, 0x48, 0x86,
                         0xf7, 0x0d, 0x01, 0x07, 0x02))
            if tail[:2] == SEQ:
                dlen = struct.unpack_from(">H", tail, 2)[0] + 4
                has = tail[4:4 + len(OID)] == OID
                kind = ("bare DER SEQUENCE %d bytes, signedData %s"
                        % (dlen, "yes" if has else "NO"))
            else:
                kind = "unrecognised (first 8: %s)" % tail[:8].hex()
        h = hashlib.sha1(tail).hexdigest()
        sizes[len(tail)] += 1
        types[kind.split(",")[0]] += 1
        blobs[h] += 1
        rows.append((p, len(d), cb, len(tail), kind, h))
        print("%-34s %10d %10d %8d %s %s"
              % (os.path.basename(p), len(d), cb, len(tail), kind[:34], h[:16]))

    print()
    print("cabinets examined      : %d" % len(rows))
    print("distinct tail lengths  : %s"
          % ", ".join("%d x%d" % (k, v) for k, v in sorted(sizes.items())))
    print("tail header recognised : %s" % dict(types))
    print("distinct tail contents : %d" % len(blobs))
    shared = {h: n for h, n in blobs.items() if n > 1}
    print("tails shared by more than one cabinet: %d (%d cabinets)"
          % (len(shared), sum(shared.values())))

    if a.names and rows:
        print()
        print("the DER of the first cabinet's tail, read as a PKCS#7:")
        p = rows[0][0]
        d = open(p, "rb").read()
        cb = struct.unpack_from("<I", d, 8)[0]
        blob = d[cb:]          # no WIN_CERTIFICATE header on a cabinet
        tmp = p + ".tail.p7b"
        open(tmp, "wb").write(blob)
        print("  written to %s (%d bytes) -- feed it to a DER reader" % (tmp, len(blob)))
        try:
            import authenticode
        except ImportError:
            return
        out, path = [], []
        authenticode.walk(blob, 0, len(blob), 0, out, path)
        prev = None
        seen = set()
        for depth, tag, text, i in out:
            if tag == "OID":
                prev = text.split()[0]
            elif tag in ("PrintableString", "UTF8String", "IA5String",
                         "BMPString") and prev in authenticode.OIDS \
                    and authenticode.OIDS[prev] in ("CN", "O", "OU", "C",
                                                    "L", "ST"):
                k = (authenticode.OIDS[prev], text)
                if k not in seen:
                    seen.add(k)
                    print("  %-4s %s" % k)
                prev = None
        for depth, tag, text, i in out:
            if tag in ("UTCTime", "GeneralizedTime"):
                print("  time %s" % text)


if __name__ == "__main__":
    main()
