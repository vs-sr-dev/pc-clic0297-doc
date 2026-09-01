#!/usr/bin/env python3
"""cdxa.py -- read RIFF/CDXA files, which are raw CD sectors wearing a WAV hat.

This repository has no disc image. It has a copied file tree, so every tool in
`tools/` that wanted sectors -- `iso9660.py`, `rawsect.py`, `padecho.py`,
`ccd.py`, `subch.py` -- had nothing to read, and the first page of this repo
says so at some length.

Three files in `PICTURES/` take part of that back.

`RIFF....CDXA` is a container Microsoft defined so that Mode 2 Form 2 sectors
could be handed around as a file: a 44-byte RIFF header, then the sectors
**raw and complete**, 2352 bytes each, sync pattern and address header
included. Which means these files still carry:

  * the 12-byte sync pattern 00 FF*10 00, so the sector boundary is verifiable
    rather than assumed;
  * the 4-byte header: minute, second, frame -- in BCD -- and the mode byte.
    That is the sector's **absolute address on the disc it was read from**, and
    converting it gives an LBA. On this material that is the only surviving
    statement about where anything physically sat;
  * the 8-byte XA subheader, twice (the spec requires it duplicated as its own
    error check): file number, channel number, submode bit flags, coding info.

So this tool measures three things the rest of the tree cannot:

  1. that the files really are sector-aligned (length divides by 2352 exactly,
     and every sync pattern lands where it should);
  2. the disc addresses, which put these sectors in a physical order and at a
     physical distance from each other;
  3. the submode flags, which say what the sectors were *for* -- real-time,
     form 2, video, audio, data, end-of-record, end-of-file.

The Form 2 payload is 2324 bytes per sector, with no EDC/ECC (that is the whole
point of Form 2: 2324 bytes of payload instead of 2048, and error correction
traded away for capacity). `--extract` writes the concatenated payload out so
whatever is inside can be identified by its own magic.

    python tools/cdxa.py FILE
    python tools/cdxa.py FILE --sectors
    python tools/cdxa.py FILE --extract OUT.bin
    python tools/cdxa.py FILE1 FILE2 ... --map
"""
import argparse
import os
import sys

SECTOR = 2352
SYNC = bytes([0x00]) + bytes([0xFF]) * 10 + bytes([0x00])
FORM2_PAYLOAD = 2324

SUBMODE_BITS = [
    (0x80, "EOF"),
    (0x40, "RT"),
    (0x20, "FORM2"),
    (0x10, "TRIGGER"),
    (0x08, "DATA"),
    (0x04, "AUDIO"),
    (0x02, "VIDEO"),
    (0x01, "EOR"),
]


def bcd(b):
    """Return the BCD byte as a decimal int, or None if it is not valid BCD."""
    hi, lo = b >> 4, b & 0x0F
    if hi > 9 or lo > 9:
        return None
    return hi * 10 + lo


def submode_names(v):
    names = [n for bit, n in SUBMODE_BITS if v & bit]
    return "|".join(names) if names else "(none)"


def parse_header(data):
    """Parse the 44-byte RIFF/CDXA header. Returns (data_offset, data_size)."""
    if data[0:4] != b"RIFF":
        return None, None, "no RIFF magic"
    riff_size = int.from_bytes(data[4:8], "little")
    if data[8:12] != b"CDXA":
        return None, None, "RIFF form is %r, not CDXA" % data[8:12]
    if data[12:16] != b"fmt ":
        return None, None, "no fmt chunk"
    fmt_size = int.from_bytes(data[16:20], "little")
    pos = 20 + fmt_size
    if data[pos:pos + 4] != b"data":
        return None, None, "no data chunk at offset %d" % pos
    data_size = int.from_bytes(data[pos + 4:pos + 8], "little")
    return pos + 8, data_size, "RIFF size %d, fmt %d bytes, data %d bytes" % (
        riff_size, fmt_size, data_size)


def read_sectors(path):
    raw = open(path, "rb").read()
    off, size, note = parse_header(raw)
    if off is None:
        return None, note, raw
    body = raw[off:off + size]
    return body, note, raw


def describe(path, show_sectors=False, extract=None):
    body, note, raw = read_sectors(path)
    print("file            : %s" % path)
    print("size            : %d bytes" % len(raw))
    if body is None:
        print("NOT a RIFF/CDXA file: %s" % note)
        return None
    print("header          : %s" % note)
    print("payload bytes   : %d" % len(body))
    n, rem = divmod(len(body), SECTOR)
    print("sectors of %d : %d, remainder %d %s"
          % (SECTOR, n, rem, "" if rem == 0 else "  <-- NOT sector aligned"))
    if len(raw) != 44 + len(body):
        print("trailing bytes  : %d after the declared data chunk"
              % (len(raw) - 44 - len(body)))

    sectors = []
    bad_sync = 0
    for i in range(n):
        s = body[i * SECTOR:(i + 1) * SECTOR]
        ok = s[0:12] == SYNC
        if not ok:
            bad_sync += 1
        m, sec, f, mode = s[12], s[13], s[14], s[15]
        sub_a = s[16:20]
        sub_b = s[20:24]
        sectors.append({
            "i": i, "sync": ok,
            "m": bcd(m), "s": bcd(sec), "f": bcd(f), "mode": mode,
            "raw_msf": (m, sec, f),
            "sub_a": sub_a, "sub_b": sub_b,
            "sub_match": sub_a == sub_b,
            "payload": s[24:24 + FORM2_PAYLOAD],
        })

    print("sync patterns   : %d of %d correct%s"
          % (n - bad_sync, n, "" if bad_sync == 0 else "   <-- %d BAD" % bad_sync))
    modes = sorted({x["mode"] for x in sectors})
    print("mode bytes      : %s" % ", ".join("0x%02X" % m for m in modes))
    mismatch = sum(1 for x in sectors if not x["sub_match"])
    print("subheader dup   : %d of %d match (the spec requires the copy)"
          % (n - mismatch, n))

    subs = {}
    for x in sectors:
        subs.setdefault(tuple(x["sub_a"]), 0)
        subs[tuple(x["sub_a"])] += 1
    print("distinct subheaders:")
    for k, c in sorted(subs.items(), key=lambda kv: -kv[1]):
        fn, ch, sm, ci = k
        print("    file=%-3d channel=%-3d submode=0x%02X %-28s coding=0x%02X   x%d"
              % (fn, ch, sm, submode_names(sm), ci, c))

    good = [x for x in sectors if None not in (x["m"], x["s"], x["f"])]
    if good:
        def lba(x):
            return (x["m"] * 60 + x["s"]) * 75 + x["f"] - 150
        first, last = good[0], good[-1]
        print("first sector MSF: %02d:%02d:%02d  ->  LBA %d"
              % (first["m"], first["s"], first["f"], lba(first)))
        print("last  sector MSF: %02d:%02d:%02d  ->  LBA %d"
              % (last["m"], last["s"], last["f"], lba(last)))
        lbas = [lba(x) for x in good]
        contiguous = all(lbas[i + 1] - lbas[i] == 1 for i in range(len(lbas) - 1))
        print("addresses       : %s"
              % ("contiguous, ascending" if contiguous else "NOT contiguous"))
        if not contiguous:
            print("    deltas: %s" % [lbas[i + 1] - lbas[i] for i in range(len(lbas) - 1)])
    else:
        print("first sector MSF: unreadable (not valid BCD)")

    head = sectors[0]["payload"][:16] if sectors else b""
    print("payload head    : %s  %r" % (head.hex(" "), head))

    if show_sectors:
        print()
        print("%-4s %-10s %-8s %-6s %-30s %s"
              % ("#", "MSF", "LBA", "mode", "submode", "payload[0:8]"))
        for x in sectors:
            if None in (x["m"], x["s"], x["f"]):
                msf, l = "BAD", "-"
            else:
                msf = "%02d:%02d:%02d" % (x["m"], x["s"], x["f"])
                l = str((x["m"] * 60 + x["s"]) * 75 + x["f"] - 150)
            print("%-4d %-10s %-8s 0x%02X   %-30s %s"
                  % (x["i"], msf, l, x["mode"],
                     submode_names(x["sub_a"][2]), x["payload"][:8].hex(" ")))

    if extract:
        with open(extract, "wb") as fh:
            for x in sectors:
                fh.write(x["payload"])
        print()
        print("wrote %d bytes of Form 2 payload to %s"
              % (n * FORM2_PAYLOAD, extract))
    return sectors


def do_map(paths):
    """Put every sector from every file onto one disc address line."""
    rows = []
    for p in paths:
        body, note, raw = read_sectors(p)
        if body is None:
            print("%s: %s" % (p, note))
            continue
        n = len(body) // SECTOR
        for i in range(n):
            s = body[i * SECTOR:(i + 1) * SECTOR]
            m, sec, f = bcd(s[12]), bcd(s[13]), bcd(s[14])
            if None in (m, sec, f):
                continue
            rows.append(((m * 60 + sec) * 75 + f - 150, os.path.basename(p), i, m, sec, f))
    rows.sort()
    print("%-9s %-10s %-24s %s" % ("LBA", "MSF", "file", "sector # within file"))
    print("-" * 9 + " " + "-" * 10 + " " + "-" * 24 + " " + "-" * 20)
    prev = None
    for lba, name, i, m, s, f in rows:
        gap = "" if prev is None else ("" if lba - prev == 1 else "   <-- gap of %d" % (lba - prev))
        print("%-9d %02d:%02d:%02d   %-24s %d%s" % (lba, m, s, f, name, i, gap))
        prev = lba
    if rows:
        print()
        print("sectors mapped : %d" % len(rows))
        print("LBA range      : %d .. %d  (span %d)"
              % (rows[0][0], rows[-1][0], rows[-1][0] - rows[0][0] + 1))


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("files", nargs="+")
    ap.add_argument("--sectors", action="store_true")
    ap.add_argument("--extract")
    ap.add_argument("--map", action="store_true")
    args = ap.parse_args()

    if args.map:
        do_map(args.files)
        return
    for i, p in enumerate(args.files):
        if i:
            print()
        describe(p, args.sectors, args.extract if len(args.files) == 1 else None)


if __name__ == "__main__":
    main()
