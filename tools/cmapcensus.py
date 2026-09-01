#!/usr/bin/env python3
"""cmapcensus.py -- the forty controller maps, read as names and as bytes.

Thirty-eight of the forty `maps\\*.cmap` members of 0compressed.zip are named
by a GUID of the shape

    B303044F-0000-0000-0000-504944564944

and 504944564944 is the ASCII of PIDVID. That is DirectInput's product GUID
for a device that reports a USB vendor/product pair: the trailing twelve hex
digits are the literal characters "PIDVID", and the leading eight are the
DWORD that carries the pair.

The question the naming raises is which half is which, and the answer is in
the byte order, not in the text. A GUID's Data1 is a little-endian DWORD; a
USB device's identity is (idVendor, idProduct) with idVendor low. So the text
form prints the DWORD big-endian-first, i.e. **product first, vendor second**,
and the two readings differ. This prints both and lets the reader pick.

It never extracts a `.big`. It reads the zip central directory for names,
sizes and CRC-32s -- which are already in the directory, uncompressed -- and
decompresses only the `.cmap` members, whose total is under 15 KB.

    python tools/cmapcensus.py E:/0compressed.zip
    python tools/cmapcensus.py E:/0compressed.zip --bytes
"""
import argparse
import collections
import hashlib
import re
import zipfile

GUIDNAME = re.compile(r"^([0-9A-Fa-f]{8})-0000-0000-0000-([0-9A-Fa-f]{12})$")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("path")
    ap.add_argument("--bytes", action="store_true",
                    help="hex-dump one representative of each content group")
    a = ap.parse_args()

    z = zipfile.ZipFile(a.path)
    infos = [i for i in z.infolist() if i.filename.lower().endswith(".cmap")]
    print("archive          : %s" % a.path)
    print("members total    : %d" % len(z.infolist()))
    print("members .cmap    : %d" % len(infos))
    print("compressed bytes : %d" % sum(i.compress_size for i in infos))
    print("stored bytes     : %d" % sum(i.file_size for i in infos))
    print()

    guids, human = [], []
    for i in infos:
        stem = i.filename.rsplit("/", 1)[-1].rsplit(chr(92), 1)[-1]
        stem = stem[:-5] if stem.lower().endswith(".cmap") else stem
        m = GUIDNAME.match(stem)
        (guids if m else human).append((i, stem, m))
    print("named by GUID    : %d" % len(guids))
    print("named by hand    : %d" % len(human))
    for i, stem, m in human:
        print("    %s   %d bytes" % (stem, i.file_size))
    print()

    tails = collections.Counter(m.group(2).upper() for i, s, m in guids)
    print("trailing twelve hex digits, and their ASCII:")
    for t, n in tails.most_common():
        try:
            txt = bytes.fromhex(t).decode("ascii")
        except (ValueError, UnicodeDecodeError):
            txt = "(not ascii)"
        print("    %s  x%-3d  = %r" % (t, n, txt))
    print()

    print("the leading DWORD, read both ways:")
    print()
    print("  %-9s %-9s  %-9s  %-9s  %s"
          % ("text", "as printed", "hi word", "lo word", "file"))
    print("  %-9s %-9s  %-9s  %-9s  %s"
          % ("", "(big-end)", "", "", ""))
    rows = []
    for i, stem, m in sorted(guids, key=lambda r: r[1]):
        d1 = int(m.group(1), 16)
        hi, lo = d1 >> 16, d1 & 0xFFFF
        rows.append((m.group(1).upper(), d1, hi, lo, i))
        print("  %-9s %-9d  0x%04X     0x%04X     %s"
              % (m.group(1).upper(), d1, hi, lo, i.filename))
    print()
    print("Read as DirectInput writes it, Data1 = (product << 16) | vendor,")
    print("so the low word is the USB vendor id and the high word the product")
    print("id. The distinct low words are the distinct vendors:")
    ven = collections.Counter("0x%04X" % r[3] for r in rows)
    for v, n in ven.most_common():
        print("    %s   %d device(s)" % (v, n))
    print()
    print("Read the other way -- high word as vendor -- the distinct values")
    print("would be:")
    ven2 = collections.Counter("0x%04X" % r[2] for r in rows)
    for v, n in ven2.most_common():
        print("    %s   %d device(s)" % (v, n))
    print("Which reading is right is not decidable from the file names alone;")
    print("it is decidable from how many distinct values each produces, and")
    print("from whether any device on the disc is also named in words.")
    print()

    print("contents: CRC-32 from the central directory, and sha1 of the")
    print("decompressed member (the .cmap files total under 15 KB):")
    print()
    groups = collections.defaultdict(list)
    for i in infos:
        data = z.read(i)
        groups[(i.file_size, hashlib.sha1(data).hexdigest())].append(i)
    print("distinct contents : %d of %d members" % (len(groups), len(infos)))
    print()
    for (size, h), members in sorted(groups.items(),
                                     key=lambda kv: -len(kv[1])):
        print("  %s  %6d bytes  x%d" % (h[:16], size, len(members)))
        for i in sorted(members, key=lambda i: i.filename):
            print("      crc %08x  %s" % (i.CRC, i.filename))
        if a.bytes:
            data = z.read(members[0])
            for o in range(0, min(len(data), 128), 16):
                row = data[o:o + 16]
                print("      %04x  %-47s  %s"
                      % (o, " ".join("%02x" % b for b in row),
                         "".join(chr(b) if 32 <= b < 127 else "."
                                 for b in row)))
        print()

    crcs = collections.Counter(i.CRC for i in infos)
    shared = {c: n for c, n in crcs.items() if n > 1}
    print("CRC-32 values shared by more than one member: %d" % len(shared))
    print("members involved                            : %d"
          % sum(shared.values()))


if __name__ == "__main__":
    main()
