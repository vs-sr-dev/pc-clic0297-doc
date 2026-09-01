#!/usr/bin/env python3
"""vds.py -- dump and compare the ISO 9660 volume descriptors of a device.

    python tools/vds.py E            dump every descriptor from sector 16 up
    python tools/vds.py E 16 17      dump two and diff them byte by byte

Reads raw 2048-byte sectors through the Windows volume device. Every field is
printed with the offset it came from, so a claim in a document can name the
byte that produced it.
"""
import sys

BS = chr(92)
NUL = bytes([0x00])

VD_TYPE = {
    0: "boot record",
    1: "primary volume descriptor",
    2: "supplementary volume descriptor",
    3: "volume partition descriptor",
    255: "volume descriptor set terminator",
}


def devpath(letter):
    return BS + BS + "." + BS + letter.upper() + ":"


def read_sector(letter, lba, n=1):
    with open(devpath(letter), "rb") as f:
        f.seek(lba * 2048)
        return f.read(2048 * n)


def strA(b):
    return b.decode("latin-1").rstrip(" ").rstrip(NUL.decode("latin-1"))


def strU(b):
    """UCS-2BE (Joliet)."""
    try:
        s = b.decode("utf-16-be")
    except UnicodeDecodeError:
        return repr(b)
    return s.rstrip(" ").rstrip("\x00")


def dt17(b):
    """17-byte dec-datetime: YYYYMMDDHHMMSShh + gmt offset byte."""
    if b[:16] == b"0" * 16 or b[:16] == b" " * 16:
        return "(unset)", None
    txt = b[:16].decode("latin-1")
    off = b[16]
    soff = off if off < 128 else off - 256
    return txt, soff


def dt7(b):
    """7-byte binary datetime from a directory record."""
    off = b[6] if b[6] < 128 else b[6] - 256
    return list(b[:6]) + [off]


def dump(letter, lba, raw=None):
    b = raw if raw is not None else read_sector(letter, lba)
    if len(b) < 2048:
        print("  sector %d: short read, %d bytes" % (lba, len(b)))
        return b
    t = b[0]
    ident = b[1:6]
    ver = b[6]
    print("sector %d" % lba)
    print("  +0    type        %d  (%s)" % (t, VD_TYPE.get(t, "?")))
    print("  +1    identifier  %r" % ident)
    print("  +6    version     %d" % ver)
    if t not in (1, 2):
        if t == 255:
            print("  (terminator, remaining %d bytes: %s)"
                  % (2048 - 7, "all zero" if b[7:] == NUL * (2048 - 7)
                     else "NOT all zero"))
        return b
    dec = strU if (t == 2) else strA
    print("  +7    flags/unused %02x" % b[7])
    print("  +8    system id   %r" % dec(b[8:40]))
    print("  +40   volume id   %r" % dec(b[40:72]))
    print("  +80   vol space   %d sectors (LE)  %d (BE)"
          % (int.from_bytes(b[80:84], "little"),
             int.from_bytes(b[84:88], "big")))
    if t == 2:
        print("  +88   escape seq  %r" % b[88:120].rstrip(NUL))
    print("  +120  set size    %d   +124 seq nr %d"
          % (int.from_bytes(b[120:122], "little"),
             int.from_bytes(b[124:126], "little")))
    print("  +128  logical blk %d" % int.from_bytes(b[128:130], "little"))
    print("  +132  path tbl sz %d" % int.from_bytes(b[132:136], "little"))
    print("  +140  L path tbl  LBA %d   (opt %d)"
          % (int.from_bytes(b[140:144], "little"),
             int.from_bytes(b[144:148], "little")))
    print("  +148  M path tbl  LBA %d   (opt %d)"
          % (int.from_bytes(b[148:152], "big"),
             int.from_bytes(b[152:156], "big")))
    rd = b[156:190]
    print("  +156  root dir    len %d, extent LBA %d, size %d bytes, flags %02x"
          % (rd[0], int.from_bytes(rd[2:6], "little"),
             int.from_bytes(rd[10:14], "little"), rd[25]))
    print("        root recorded %s" % dt7(rd[18:25]))
    for off, name, ln in ((190, "volume set", 128), (318, "publisher", 128),
                          (446, "preparer", 128), (574, "application", 128),
                          (702, "copyright file", 37), (739, "abstract file", 37),
                          (776, "biblio file", 37)):
        v = dec(b[off:off + ln])
        print("  +%-4d %-14s %s" % (off, name, repr(v) if v else "'' (EMPTY)"))
    for off, name in ((813, "creation"), (830, "modification"),
                      (847, "expiration"), (864, "effective")):
        txt, o = dt17(b[off:off + 17])
        if o is None:
            print("  +%-4d %-14s %s" % (off, name, txt))
        else:
            print("  +%-4d %-14s %s  gmt offset %d (= UTC%+g)"
                  % (off, name, txt, o, o * 0.25))
    print("  +881  file struct version %d" % b[881])
    app = b[883:1395]
    print("  +883  application use  %s"
          % ("all zero" if app == NUL * 512
             else "NOT all zero: %r..." % app[:48]))
    res = b[1395:2048]
    print("  +1395 reserved        %s"
          % ("all zero" if res == NUL * 653
             else "NOT all zero: %r..." % res[:48]))
    return b


def diff(letter, a, bb):
    ba = read_sector(letter, a)
    bc = read_sector(letter, bb)
    print()
    print("=" * 70)
    print("byte-by-byte comparison of sector %d and sector %d" % (a, bb))
    print("=" * 70)
    if ba == bc:
        print("IDENTICAL. All 2048 bytes equal.")
        import hashlib
        print("sha1 of both: %s" % hashlib.sha1(ba).hexdigest())
        return
    d = [i for i in range(2048) if ba[i] != bc[i]]
    print("DIFFERENT in %d of 2048 bytes." % len(d))
    runs = []
    for i in d:
        if runs and i == runs[-1][1] + 1:
            runs[-1][1] = i
        else:
            runs.append([i, i])
    for s, e in runs:
        print("  offset %4d..%-4d (%d bytes)" % (s, e, e - s + 1))
        print("     sector %d: %s  %r" % (a, ba[s:e + 1].hex(" "), ba[s:e + 1]))
        print("     sector %d: %s  %r" % (bb, bc[s:e + 1].hex(" "), bc[s:e + 1]))


def main():
    letter = sys.argv[1] if len(sys.argv) > 1 else "E"
    if len(sys.argv) > 3:
        a, b = int(sys.argv[2]), int(sys.argv[3])
        dump(letter, a)
        print()
        dump(letter, b)
        diff(letter, a, b)
        return
    lba = 16
    while lba < 40:
        b = dump(letter, lba)
        print()
        if len(b) >= 7 and b[0] == 255:
            break
        if len(b) < 7 or b[1:6] != b"CD001":
            break
        lba += 1


if __name__ == "__main__":
    main()
