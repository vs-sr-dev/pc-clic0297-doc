#!/usr/bin/env python3
"""clocks.py -- the three clocks in this image, and the subtraction between them.

The disc declares two different time zones for the same instant: the volume
descriptor says GMT+0 and the directory records say +4 quarter-hours, which is
UTC+1. Nothing inside the ISO can settle that, because the burn is one event
with one timestamp.

The settlement comes from two clocks that are not the burner's:

  * Inno Setup records each source file's modification time and records, in a
    flag on the same record, whether that time is UTC. `foTimeStampInUTC` is
    bit 2 of the 16-bit Flags field;
  * a Microsoft PE carries a COFF header timestamp, which is seconds since the
    Unix epoch, has no zone field, and is written by the linker in UTC.

The game executable appears in both. Subtract, and the offset falls out.

Usage:
    python tools/clocks.py IMAGE INSTALLER GAMEEXE
"""
import datetime
import struct
import sys

sys.path.insert(0, __file__.rsplit(chr(92), 1)[0] if chr(92) in __file__
                else __file__.rsplit("/", 1)[0])
import inno  # noqa: E402

SECTOR = 2048


def iso_fields(image):
    with open(image, "rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        f.seek(17 * SECTOR)
        svd = f.read(SECTOR)
    out = {}
    for name, d in (("primary", pvd), ("supplementary", svd)):
        out[name] = {
            "creation_raw": d[813:830],
            "creation": d[813:829].decode("ascii", "replace"),
            "tz_offset_quarters": d[829],
        }
    return out


def dir_records(image):
    """Every directory record in the root and its two children, with the
    seven raw date bytes and the timezone byte."""
    with open(image, "rb") as f:
        f.seek(16 * SECTOR)
        pvd = f.read(SECTOR)
        root_lba = struct.unpack("<I", pvd[158:162])[0]
        out = []
        todo = [root_lba]
        seen = set()
        while todo:
            lba = todo.pop(0)
            if lba in seen:
                continue
            seen.add(lba)
            f.seek(lba * SECTOR)
            data = f.read(SECTOR)
            off = 0
            while off < len(data) and data[off]:
                rl = data[off]
                ex = struct.unpack("<I", data[off + 2:off + 6])[0]
                date = data[off + 18:off + 25]
                flags = data[off + 25]
                nl = data[off + 32]
                name = data[off + 33:off + 33 + nl]
                if nl > 1:
                    out.append((name.decode("ascii", "replace"), date, flags))
                    if flags & 2:
                        todo.append(ex)
                off += rl
    return out


def fmt_date(d):
    if not any(d):
        return "(all seven bytes zero)", None
    y, mo, da, h, mi, s, tz = d
    return ("%04d-%02d-%02d %02d:%02d:%02d" % (1900 + y, mo, da, h, mi, s)), tz


def main():
    image, installer, gameexe = sys.argv[1], sys.argv[2], sys.argv[3]

    print("=== clock 1: the ISO, written by Burn4Free ===")
    for name, v in iso_fields(image).items():
        print("  %-14s creation %s  timezone field %d quarter-hours"
              % (name, v["creation"], v["tz_offset_quarters"]))
    print()
    for name, date, flags in dir_records(image):
        text, tz = fmt_date(date)
        print("  %-24s %-30s tz %s"
              % (name, text, "-" if tz is None else "%+d quarter-hours = UTC%+d"
                 % (tz, tz // 4)))
    print()

    print("=== clock 2: Inno Setup, inside the installer ===")
    files, data = inno.joined(installer)
    utc_flagged = sum(1 for r in data if r["flags"] & 4)
    print("  file location entries          : %d" % len(data))
    print("  carrying foTimeStampInUTC      : %d" % utc_flagged)
    print("  therefore the timestamps are   : %s"
          % ("UTC" if utc_flagged == len(data) else "LOCAL time"))
    stamped = sorted((inno.filetime_to_iso(e["data"]["filetime"]), e["dest"])
                     for e in files if e["data"])
    print("  earliest                       : %s  %s" % stamped[0])
    print("  latest                         : %s  %s" % stamped[-1])
    game = [e for e in files
            if e["dest"].lower().endswith(chr(92) + "lucignolo.exe")]
    game_ts = inno.filetime_to_iso(game[0]["data"]["filetime"]) if game else None
    print("  the game executable            : %s" % game_ts)
    print()

    print("=== clock 3: the PE COFF header, written by the linker in UTC ===")
    with open(gameexe, "rb") as f:
        d = f.read(1024)
    e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
    coff = struct.unpack_from("<I", d, e_lfanew + 8)[0]
    utc = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=coff)
    print("  COFF timestamp                 : %d = %s UTC"
          % (coff, utc.strftime("%Y-%m-%d %H:%M:%S")))
    print()

    print("=== the subtraction ===")
    if game_ts:
        local = datetime.datetime.strptime(game_ts[:19], "%Y-%m-%d %H:%M:%S")
        delta = local - utc
        print("  Inno (local) minus COFF (UTC)  : %s" % delta)
        print("  so local time is               : UTC%+d, with %d s of"
              " link-to-close lag"
              % (round(delta.total_seconds() / 3600.0),
                 3600 - int(delta.total_seconds()) % 3600))
    print()
    print("=== how long the installer took to build ===")
    last = datetime.datetime.strptime(stamped[-1][0][:19], "%Y-%m-%d %H:%M:%S")
    for name, date, flags in dir_records(image):
        if name.upper().startswith("LUCIGNOLO.EXE"):
            text, tz = fmt_date(date)
            closed = datetime.datetime.strptime(text, "%Y-%m-%d %H:%M:%S")
            print("  last source file packed        : %s  %s" % stamped[-1])
            print("  installer's own mtime on disc  : %s (tz %+d quarter-hours)"
                  % (text, tz))
            print("  elapsed                        : %s" % (closed - last))


if __name__ == "__main__":
    main()
