#!/usr/bin/env python3
"""dates.py -- what else could the seven bytes be?

`iso9660.py --verify-record` establishes that the seven bytes at offset 18 of
a directory record are where ECMA-119 says the recording date is: the two
both-endian fields on either side of them agree, the declared record length
accounts for every byte, and the two namespaces carry the same seven bytes.
So the parser is right and the values are real.

Three of the eleven distinct values are nevertheless impossible as ECMA-119
dates -- month 230, day 0, hour 192. This tool takes each distinct value and
runs it through every other timestamp encoding a Windows or DOS program of
the period could plausibly have written into seven bytes, printing what each
one yields. Anything landing between 1995 and 2005 is flagged.

It is a search for an explanation, and it does not find one. The output is
kept because "here are the twenty-two encodings that do not explain it" is
worth more to the next person than silence.

    python tools/dates.py IMAGE
"""
import datetime
import struct
import sys
from collections import Counter

sys.path.insert(0, __file__.rsplit("iso", 1)[0])

LOW = datetime.datetime(1995, 1, 1)
HIGH = datetime.datetime(2005, 1, 1)


def plausible(dt):
    return dt is not None and LOW <= dt <= HIGH


def try_unix(v):
    try:
        return datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=v)
    except Exception:
        return None


def try_filetime(v):
    try:
        return (datetime.datetime(1601, 1, 1) +
                datetime.timedelta(microseconds=v // 10))
    except Exception:
        return None


def try_dosdate(d, t):
    try:
        return datetime.datetime(1980 + (d >> 9), (d >> 5) & 15, d & 31,
                                 t >> 11, (t >> 5) & 63, (t & 31) * 2)
    except Exception:
        return None


def try_ecma(b):
    try:
        return datetime.datetime(1900 + b[0], b[1], b[2], b[3], b[4], b[5])
    except Exception:
        return None


def attempts(b):
    """(name, datetime or None) for every reading tried."""
    out = [("ECMA-119 as written", try_ecma(b))]
    for off in (0, 1, 2, 3):
        for endian in ("<", ">"):
            if off + 4 <= 7:
                v = struct.unpack_from(endian + "I", b, off)[0]
                out.append(("time_t %s at +%d" % (
                    "LE" if endian == "<" else "BE", off), try_unix(v)))
    for hi in (0x00, 0x01, 0x02):
        v = int.from_bytes(bytes(b) + bytes([hi]), "little")
        out.append(("FILETIME LE, 8th byte 0x%02X" % hi, try_filetime(v)))
        v = int.from_bytes(bytes([hi]) + bytes(b), "big")
        out.append(("FILETIME BE, 1st byte 0x%02X" % hi, try_filetime(v)))
    for off in (0, 1, 2, 3):
        if off + 4 <= 7:
            t = struct.unpack_from("<H", b, off)[0]
            d = struct.unpack_from("<H", b, off + 2)[0]
            out.append(("DOS time,date LE at +%d" % off, try_dosdate(d, t)))
            out.append(("DOS date,time LE at +%d" % off, try_dosdate(t, d)))
            t = struct.unpack_from(">H", b, off)[0]
            d = struct.unpack_from(">H", b, off + 2)[0]
            out.append(("DOS time,date BE at +%d" % off, try_dosdate(d, t)))
            out.append(("DOS date,time BE at +%d" % off, try_dosdate(t, d)))
    out.append(("ECMA-119 on bytes reversed", try_ecma(bytes(b)[::-1])))
    out.append(("ECMA-119 shifted one byte left", try_ecma(bytes(b)[1:] + b"\0")))
    out.append(("ECMA-119 shifted one byte right",
                try_ecma(b"\0" + bytes(b)[:6])))
    out.append(("ECMA-119 with year read as BCD",
                try_ecma(bytes([((b[0] >> 4) * 10 + (b[0] & 15)) & 0xFF]) +
                         bytes(b)[1:])))
    return out


def main():
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    import os
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    import iso9660 as I
    fh, mm = I.open_image(sys.argv[1])
    vds = I.read_vds(mm)
    entries = I.tree_of(mm, vds, False)
    c = Counter(e["raw7"] for e in entries)
    print("distinct seven-byte values on %d directory records: %d" % (
        len(entries), len(c)))
    print()
    hits = 0
    for raw, n in c.most_common():
        good = I.date_is_valid(raw)
        print("=" * 74)
        print("%s   x%d   %s" % (
            " ".join("%02X" % x for x in raw), n,
            "valid ECMA-119 date" if good else "IMPOSSIBLE as ECMA-119"))
        print("=" * 74)
        for name, dt in attempts(raw):
            mark = ""
            if plausible(dt):
                mark = "   <-- lands in 1995..2005"
                hits += 1
            print("   %-34s %s%s" % (
                name, dt.strftime("%Y-%m-%d %H:%M:%S") if dt else "-", mark))
        print()
    print("readings that produced a date between 1995 and 2005: %d" % hits)
    print()
    print("The ECMA-119 reading is the one the standard specifies and the")
    print("one --verify-record proves is aligned. Every other line above is")
    print("a hypothesis being eliminated, not a candidate being offered.")
    mm.close()
    fh.close()


if __name__ == "__main__":
    main()
