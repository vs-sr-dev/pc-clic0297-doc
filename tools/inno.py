#!/usr/bin/env python3
"""inno.py -- an Inno Setup 5.2.1 reader, written for this disc.

Both executables on this disc are Inno Setup 5.2.1 installers built by the
same copy of the compiler: `setup.exe` (303,866 bytes) and
`Installer/Lucignolo.exe` (1,078,935,840 bytes). This tool reads both with
the standard library only -- `lzma`, `zlib`, `bz2` and `struct` -- because
Inno's three compression choices are all in it.

--------------------------------------------------------------------------
WHAT THE FILE LOOKS LIKE, AS MEASURED RATHER THAN AS REMEMBERED
--------------------------------------------------------------------------

A SetupLdr executable is a small Delphi stub whose PE sections end early;
everything after them is data. The stub carries a 44-byte table at a fixed
offset that says where the three data areas start:

    0xC988  ID          12 bytes  'rDlPtS' + CD E6 D7 7B 0B 2A
            Version      uint32   1
            TotalSize    uint32   == the size of the whole .exe
            OffsetEXE    uint32   compressed setup.e32
            UncompressedSizeEXE   uint32
            CRCEXE       uint32
            Offset0      uint32   the setup *header* block
            Offset1      uint32   the compressed *file data* block
            TableCRC     uint32

The layout that both files on this disc actually have is

    [ stub | file data @Offset1 | setup header @Offset0 | setup.e32 @OffsetEXE ]

with the file data BEFORE the header, not after it. On `setup.exe`
Offset0 == Offset1 == 54,272, and the four areas add up to the file size with
nothing left over, which is what proves that its file-data area is empty:
54,272 + 20,504 + 229,090 = 303,866.

A block at Offset0 begins with a 64-byte NUL-padded identification string,
`Inno Setup Setup Data (5.2.1)`. A block at Offset1 or OffsetEXE has no such
string. After the string (or immediately, for the other two) comes the block
framing:

    uint32  CRC-32 of the next 5 bytes
    uint32  stored_size -- the framed size, INCLUDING the per-chunk CRCs
    uint8   compressed: 1 = LZMA1, 0 = stored

and then the framed stream itself, as a sequence of

    uint32  CRC-32 of the chunk
    bytes   up to 4096 bytes of chunk

The first four bytes of the *unframed* stream, when compressed==1, are not
LZMA data: they are LZMA1 properties (1 byte) plus dictionary size (uint32),
i.e. the first five bytes of a `.lzma` header without the eight-byte size
field. `zlb\x1a` at Offset1 is a *different* wrapper -- see below.

--------------------------------------------------------------------------
THE THREE THINGS THIS GOT WRONG BEFORE IT GOT THEM RIGHT
--------------------------------------------------------------------------

1. **The offset table was read one field short.** The first version mapped
   the 32 bytes after the ID onto seven uint32s starting at TotalSize, which
   made `Offset0` come out as 0xAEA434B7 -- 2.9 GB into a 1.07 GB file. The
   table has *eight* uint32s, not seven: there is a `Version` field (value 1)
   between the ID and TotalSize. The tell was that the bogus reading put
   `TotalSize` at 1 and `CRCEXE` at 681,984, which is a suspiciously round
   number for a checksum and is in fact the uncompressed size of setup.e32.
   A CRC that looks like a size means the window has slipped.

2. **`lzma.FORMAT_ALONE` was fed the framed stream.** The per-chunk CRC-32s
   are interleaved *inside* the compressed data, every 4096 bytes. Handing
   the raw region to the decompressor decodes the first chunk and then fails
   on `_lzma.LZMAError: Corrupt input data` at a position that is always a
   multiple of 4096 plus a few bytes -- which is the diagnostic. The frame
   has to be stripped first, and only then does the LZMA stream begin.

3. **`FORMAT_ALONE` needs a 13-byte header and Inno stores 5.** Inno writes
   the properties byte and the dictionary size and stops; there is no
   uncompressed-size field. Prepending eight 0xFF bytes -- the `.lzma`
   convention for "size unknown" -- makes FORMAT_ALONE accept it, and avoids
   having to unpack the properties byte into lc/lp/pb for FORMAT_RAW. Both
   routes are implemented below and `--check-lzma` runs them against each
   other, because a decompressor that agrees with itself is worth more than
   one that merely returns bytes.

Usage:
    python tools/inno.py FILE --ldr
    python tools/inno.py FILE --blocks
    python tools/inno.py FILE --header [--save OUT.bin]
    python tools/inno.py FILE --strings [--min N]
    python tools/inno.py FILE --check-lzma
    python tools/inno.py FILE --verify-entries
    python tools/inno.py FILE --flags
    python tools/inno.py FILE --files
    python tools/inno.py FILE --census
    python tools/inno.py FILE --extract OUTDIR [--only PREFIX]
"""
import binascii
import bz2
import lzma
import os
import struct
import sys
import zlib

LDR_TABLE_OFFSET = 0xC988
LDR_ID = b"rDlPtS\xcd\xe6\xd7\x7b\x0b\x2a"
CHUNK = 4096


class InnoError(Exception):
    pass


def read_offset_table(path):
    with open(path, "rb") as f:
        f.seek(LDR_TABLE_OFFSET)
        raw = f.read(44)
    if raw[:12] != LDR_ID:
        raise InnoError("no SetupLdrOffsetTable ID at 0x%X: got %r"
                        % (LDR_TABLE_OFFSET, raw[:12]))
    (version, total_size, offset_exe, uncompressed_exe, crc_exe,
     offset0, offset1, table_crc) = struct.unpack("<8I", raw[12:44])
    computed = binascii.crc32(raw[:40]) & 0xFFFFFFFF
    return {
        "raw": raw,
        "version": version,
        "total_size": total_size,
        "offset_exe": offset_exe,
        "uncompressed_exe": uncompressed_exe,
        "crc_exe": crc_exe,
        "offset0": offset0,
        "offset1": offset1,
        "table_crc": table_crc,
        "table_crc_computed": computed,
        "file_size": os.path.getsize(path),
    }


def lzma_alone(data):
    """Inno stores 5 bytes of LZMA1 properties. FORMAT_ALONE wants 13."""
    header = data[:5] + b"\xff" * 8
    d = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
    return d.decompress(header + data[5:])


def lzma_raw(data):
    """The same stream through FORMAT_RAW, unpacking the properties byte by
    hand. Kept so that --check-lzma can compare two independent routes."""
    props = data[0]
    if props >= 9 * 5 * 5:
        raise InnoError("LZMA properties byte 0x%02X out of range" % props)
    lc = props % 9
    rem = props // 9
    lp = rem % 5
    pb = rem // 5
    dict_size = struct.unpack("<I", data[1:5])[0]
    filters = [{"id": lzma.FILTER_LZMA1, "lc": lc, "lp": lp, "pb": pb,
                "dict_size": max(dict_size, 4096)}]
    d = lzma.LZMADecompressor(format=lzma.FORMAT_RAW, filters=filters)
    return d.decompress(data[5:])


def lzma_props(data):
    props = data[0]
    lc = props % 9
    lp = (props // 9) % 5
    pb = (props // 9) // 5
    return props, lc, lp, pb, struct.unpack("<I", data[1:5])[0]


def unframe(blob, stored_size):
    """Strip the 4-byte CRC that precedes every 4,096-byte chunk.

    Returns (payload, [(chunk_index, stored_crc, computed_crc), ...]) so the
    caller can report how many chunks failed instead of only that one did."""
    out = bytearray()
    checks = []
    pos = 0
    idx = 0
    while pos < stored_size:
        if pos + 4 > stored_size:
            raise InnoError("chunk %d: truncated CRC at %d" % (idx, pos))
        stored = struct.unpack("<I", blob[pos:pos + 4])[0]
        pos += 4
        n = min(CHUNK, stored_size - pos)
        chunk = blob[pos:pos + n]
        pos += n
        computed = binascii.crc32(chunk) & 0xFFFFFFFF
        checks.append((idx, stored, computed))
        out += chunk
        idx += 1
    return bytes(out), checks


def read_block(path, offset, expect_id=False):
    """Read one Inno block. Returns a dict with everything measured."""
    f = open(path, "rb")
    f.seek(offset)
    info = {"offset": offset}
    if expect_id:
        ident = f.read(64)
        info["id"] = ident.rstrip(b"\x00")
        info["id_padding_ok"] = set(ident[len(info["id"]):]) <= {0}
        header_at = offset + 64
    else:
        info["id"] = None
        header_at = offset
    head = f.read(9)
    crc_stored = struct.unpack("<I", head[0:4])[0]
    stored_size, compressed = struct.unpack("<IB", head[4:9])
    crc_computed = binascii.crc32(head[4:9]) & 0xFFFFFFFF
    info.update({
        "header_at": header_at,
        "header_crc": crc_stored,
        "header_crc_computed": crc_computed,
        "header_crc_ok": crc_stored == crc_computed,
        "stored_size": stored_size,
        "compressed": compressed,
        "data_at": header_at + 9,
        "block_end": header_at + 9 + stored_size,
    })
    blob = f.read(stored_size)
    f.close()
    if len(blob) < stored_size:
        raise InnoError("block at %d: wanted %d framed bytes, file gave %d"
                        % (offset, stored_size, len(blob)))
    payload, checks = unframe(blob, stored_size)
    info["chunks"] = len(checks)
    info["chunks_bad"] = [c for c in checks if c[1] != c[2]]
    info["framed_payload"] = payload
    if compressed:
        info["lzma_props"] = lzma_props(payload)
        info["data"] = lzma_alone(payload)
    else:
        info["lzma_props"] = None
        info["data"] = payload
    return info


def cmd_ldr(path):
    t = read_offset_table(path)
    print("file                : %s" % path)
    print("file size           : %d" % t["file_size"])
    print("table at            : 0x%X" % LDR_TABLE_OFFSET)
    print("ID                  : %r  OK" % t["raw"][:12])
    print("Version             : %d" % t["version"])
    print("TotalSize           : %d   %s" % (
        t["total_size"],
        "== file size" if t["total_size"] == t["file_size"] else "!= FILE SIZE"))
    print("OffsetEXE           : %d" % t["offset_exe"])
    print("UncompressedSizeEXE : %d" % t["uncompressed_exe"])
    print("CRCEXE              : 0x%08X" % t["crc_exe"])
    print("Offset0 (header)    : %d" % t["offset0"])
    print("Offset1 (file data) : %d" % t["offset1"])
    print("TableCRC            : 0x%08X   computed 0x%08X   %s" % (
        t["table_crc"], t["table_crc_computed"],
        "OK" if t["table_crc"] == t["table_crc_computed"] else "MISMATCH"))
    print()
    print("accounting, in file order:")
    parts = [("stub + PE sections", 0, t["offset1"]),
             ("file data", t["offset1"], t["offset0"]),
             ("setup header", t["offset0"], t["offset_exe"]),
             ("compressed setup.e32", t["offset_exe"], t["file_size"])]
    total = 0
    for name, a, b in parts:
        print("  %-22s %12d .. %-12d %12d bytes" % (name, a, b, b - a))
        total += b - a
    print("  %-22s %38d bytes  %s" % ("sum", total,
          "== file size" if total == t["file_size"] else "!= FILE SIZE"))


def cmd_blocks(path):
    t = read_offset_table(path)
    for label, off, want_id in (("setup header", t["offset0"], True),
                                ("setup.e32", t["offset_exe"], False)):
        print("=== %s at %d ===" % (label, off))
        b = read_block(path, off, expect_id=want_id)
        if b["id"] is not None:
            print("  identification    : %r  (padding all NUL: %s)"
                  % (b["id"], b["id_padding_ok"]))
        print("  header CRC        : 0x%08X computed 0x%08X  %s" % (
            b["header_crc"], b["header_crc_computed"],
            "OK" if b["header_crc_ok"] else "MISMATCH"))
        print("  stored_size       : %d (framed)" % b["stored_size"])
        print("  compressed flag   : %d  (%s)" % (
            b["compressed"], "LZMA1" if b["compressed"] else "stored"))
        print("  chunks of %d     : %d, %d with a bad CRC"
              % (CHUNK, b["chunks"], len(b["chunks_bad"])))
        if b["lzma_props"]:
            p, lc, lp, pb, ds = b["lzma_props"]
            print("  LZMA1 properties  : 0x%02X  lc=%d lp=%d pb=%d dict=%d"
                  % (p, lc, lp, pb, ds))
        print("  unframed          : %d bytes" % len(b["framed_payload"]))
        print("  decompressed      : %d bytes" % len(b["data"]))
        print("  ratio             : %.4fx" % (
            len(b["data"]) / float(b["block_end"] - off)))
        if label == "setup.e32":
            print("  matches UncompressedSizeEXE : %s"
                  % (len(b["data"]) == t["uncompressed_exe"]))
            crc = binascii.crc32(b["data"]) & 0xFFFFFFFF
            print("  CRC-32 of result  : 0x%08X  declared 0x%08X  %s" % (
                crc, t["crc_exe"], "OK" if crc == t["crc_exe"] else "MISMATCH"))
        print()


def cmd_header(path, save=None):
    t = read_offset_table(path)
    b = read_block(path, t["offset0"], expect_id=True)
    data = b["data"]
    print("identification      : %r" % b["id"])
    print("decompressed header : %d bytes" % len(data))
    if save:
        with open(save, "wb") as f:
            f.write(data)
        print("written to          : %s" % save)


def cmd_strings(path, minlen=4):
    """Walk the decompressed header as Inno stores it: uint32 length followed
    by that many bytes. This is deliberately schema-free -- it does not need
    to know the field order of TSetupHeader, and so it cannot silently drift
    out of step with a version it was not written for. Runs that do not parse
    as a plausible string are skipped one byte at a time."""
    t = read_offset_table(path)
    data = read_block(path, t["offset0"], expect_id=True)["data"]
    n = len(data)
    i = 0
    while i + 4 <= n:
        ln = struct.unpack("<I", data[i:i + 4])[0]
        if minlen <= ln <= 4096 and i + 4 + ln <= n:
            s = data[i + 4:i + 4 + ln]
            if all(0x20 <= c < 0x7F or c in (9, 10, 13) or c >= 0xA0
                   for c in s):
                try:
                    txt = s.decode("cp1252")
                except UnicodeDecodeError:
                    txt = repr(s)
                print("%8d  %5d  %s" % (i, ln, txt))
                i += 4 + ln
                continue
        i += 1


def cmd_check_lzma(path):
    t = read_offset_table(path)
    b = read_block(path, t["offset0"], expect_id=True)
    payload = b["framed_payload"]
    a = lzma_alone(payload)
    try:
        r = lzma_raw(payload)
    except Exception as exc:
        print("FORMAT_RAW route failed: %s" % exc)
        return
    print("FORMAT_ALONE : %d bytes" % len(a))
    print("FORMAT_RAW   : %d bytes" % len(r))
    print("identical    : %s" % (a == r))
    print("zlib route   : %s" % _try(zlib.decompress, payload))
    print("bz2 route    : %s" % _try(bz2.decompress, payload))


def _try(fn, data):
    try:
        return "%d bytes" % len(fn(data))
    except Exception as exc:
        return "fails (%s)" % type(exc).__name__


# --------------------------------------------------------------------------
# Entries.
#
# There are two arrays and they live in two different blocks.
#
# Block A, at Offset0, holds TSetupHeader followed by every entry array in
# turn: languages, messages, permissions, types, components, tasks, dirs,
# FILES, icons, ini, registry, delete, uninstall-delete, run, uninstall-run.
# Block B, immediately after A and ending exactly at OffsetEXE, holds the
# TSetupFileLocationEntry array and nothing else.
#
# A TSetupFileEntry for 5.2.1, with the field widths as measured on this
# file rather than as recalled:
#
#     u32 len + bytes   SourceFilename      (empty when compressed)
#     u32 len + bytes   DestName
#     u32 len + bytes   InstallFontName     (empty here)
#     6 x (u32 len + bytes)                 Components, Tasks, Languages,
#                                           Check, AfterInstall, BeforeInstall
#     20 bytes          TSetupVersionData   (two 10-byte Windows versions)
#     u32               LocationEntry       index into the block-B array
#     u32               Attribs
#     u64               ExternalSize
#     i16               PermissionsEntry    (-1 = none)
#     u32               Options
#     u8                FileType
#
# which is 79 bytes plus the three name lengths. That total was not assumed:
# it was derived by taking the gaps between consecutive DestName strings
# found by --strings and subtracting their lengths, which came out at a
# constant 79 for every pair. The layout above is then confirmed by the
# LocationEntry field, which must read 0, 1, 2, 3 ... on a setup whose files
# were compiled in order -- and does. `--verify-entries` re-runs that check.
#
# A TSetupFileLocationEntry is a fixed 70 bytes:
#
#     u32 FirstSlice, u32 LastSlice, u32 StartOffset,
#     u64 ChunkSuboffset, u64 OriginalSize, u64 ChunkCompressedSize,
#     16 bytes MD5, u64 FILETIME SourceTimeStamp,
#     u32 FileVersionMS, u32 FileVersionLS, u16 Flags
#
# 70 was not assumed either: block B decompresses to 170,800 bytes, and of
# the plausible strides only 70 divides it without remainder -- 2,440 times.
# The 20-byte SHA-1 variant that Inno adopted at 5.3.9 would give 74, and 74
# does not divide 170,800. That is how this file dates itself.
# --------------------------------------------------------------------------

FILE_ENTRY_FIXED = 79
DATA_ENTRY_SIZE = 70

FILE_FLAG_NAMES = [
    "ConfirmOverwrite", "NeverUninstall", "RestartReplace", "DeleteAfterInstall",
    "RegisterServer", "RegisterTypeLib", "SharedFile", "CompareTimeStamp",
    "FontIsNotTrueType", "SkipIfSourceDoesntExist", "OverwriteReadOnly",
    "OverwriteSameVersion", "CustomDestName", "OnlyIfDestFileExists",
    "NoRegError", "UninsRestartDelete", "OnlyIfDoesntExist", "IgnoreVersion",
    "PromptIfOlder", "DontCopy", "UninsRemoveReadOnly", "RecurseSubDirsExternal",
    "ReplaceSameVersionIfContentsDiffer", "DontVerifyChecksum",
    "UninsNoSharedFilePrompt", "CreateAllSubDirs", "Bits32", "Bits64",
    "ExternalSizePreset", "SetNTFSCompression", "UnsetNTFSCompression",
    "GacInstall",
]

DATA_FLAG_NAMES = [
    "VersionInfoValid", "VersionInfoNotValid", "TimeStampInUTC", "IsUninstExe",
    "CallInstructionOptimized", "Touch", "ChunkEncrypted", "ChunkCompressed",
    "SolidBreak",
]


def _rdstr(d, q):
    n = struct.unpack("<I", d[q:q + 4])[0]
    return d[q + 4:q + 4 + n], q + 4 + n


def parse_file_entry(d, off):
    src, q = _rdstr(d, off)
    dest, q = _rdstr(d, q)
    font, q = _rdstr(d, q)
    conds = []
    for _ in range(6):
        s, q = _rdstr(d, q)
        conds.append(s)
    version_data = d[q:q + 20]
    q += 20
    location, attribs = struct.unpack("<2I", d[q:q + 8])
    q += 8
    external_size = struct.unpack("<Q", d[q:q + 8])[0]
    q += 8
    permission = struct.unpack("<h", d[q:q + 2])[0]
    q += 2
    options = struct.unpack("<I", d[q:q + 4])[0]
    q += 4
    file_type = d[q]
    q += 1
    return {
        "source": src, "dest": dest.decode("cp1252", "replace"),
        "font": font, "conditions": conds, "version_data": version_data,
        "location": location, "attribs": attribs,
        "external_size": external_size, "permission": permission,
        "options": options, "type": file_type, "start": off, "end": q,
    }


def find_file_entries(d, probe=20):
    """Locate the start of the TSetupFileEntry array without knowing the
    layout of everything that precedes it.

    The test is that `probe` consecutive records must parse with LocationEntry
    running 0, 1, 2, ... and with a DestName that begins with a constant
    directory reference. Anything that satisfies that for twenty records in a
    row is the array; nothing else on this file does."""
    n = len(d)
    for off in range(0, n - 200):
        if d[off:off + 4] != b"\x00\x00\x00\x00":
            continue
        try:
            q = off
            ok = True
            for k in range(probe):
                e = parse_file_entry(d, q)
                if e["location"] != k or not e["dest"].startswith("{"):
                    ok = False
                    break
                if e["end"] - e["start"] != FILE_ENTRY_FIXED + len(e["dest"]):
                    ok = False
                    break
                q = e["end"]
            if ok:
                return off
        except (struct.error, IndexError):
            continue
    raise InnoError("could not locate the file entry array")


def read_file_entries(path):
    t = read_offset_table(path)
    d = read_block(path, t["offset0"], expect_id=True)["data"]
    if t["offset0"] == t["offset1"]:
        # The header block begins where the file-data area begins, so the
        # file-data area is empty and there is nothing for a file entry to
        # point at. `setup.exe` on this disc is exactly that: an installer
        # with no payload. Returning empty here is the measurement, not a
        # failure to parse -- see docs/03.
        return [], None, None, d
    off = find_file_entries(d)
    entries = []
    q = off
    while q < len(d):
        try:
            e = parse_file_entry(d, q)
        except (struct.error, IndexError):
            break
        if not e["dest"].startswith("{") or e["location"] != len(entries):
            break
        entries.append(e)
        q = e["end"]
    return entries, off, q, d


def read_data_entries(path):
    t = read_offset_table(path)
    a = read_block(path, t["offset0"], expect_id=True)
    b = read_block(path, a["block_end"], expect_id=False)
    d = b["data"]
    if len(d) % DATA_ENTRY_SIZE:
        raise InnoError("data entry block is %d bytes, not a multiple of %d"
                        % (len(d), DATA_ENTRY_SIZE))
    out = []
    for i in range(0, len(d), DATA_ENTRY_SIZE):
        r = d[i:i + DATA_ENTRY_SIZE]
        first, last, start = struct.unpack("<3I", r[0:12])
        sub, orig, comp = struct.unpack("<3Q", r[12:36])
        md5 = r[36:52]
        ft = struct.unpack("<Q", r[52:60])[0]
        vms, vls = struct.unpack("<2I", r[60:68])
        flags = struct.unpack("<H", r[68:70])[0]
        out.append({
            "first_slice": first, "last_slice": last, "start_offset": start,
            "chunk_suboffset": sub, "original_size": orig,
            "chunk_compressed_size": comp, "md5": md5, "filetime": ft,
            "version_ms": vms, "version_ls": vls, "flags": flags,
        })
    return out, b


def filetime_to_iso(ft):
    """FILETIME is 100 ns ticks since 1601-01-01. Returned as a naive string
    with no timezone applied, because whether it is UTC is a flag on the
    record and the caller has to decide what to do about it."""
    if ft == 0:
        return "(unset)"
    secs, rem = divmod(ft, 10000000)
    secs -= 11644473600
    import datetime
    try:
        dt = datetime.datetime(1970, 1, 1) + datetime.timedelta(seconds=secs)
    except OverflowError:
        return "(out of range: %d)" % ft
    return dt.strftime("%Y-%m-%d %H:%M:%S") + (".%07d" % rem if rem else "")


def joined(path):
    files, _, _, _ = read_file_entries(path)
    data, _ = read_data_entries(path)
    for e in files:
        loc = e["location"]
        e["data"] = data[loc] if loc < len(data) else None
    return files, data


def cmd_verify_entries(path):
    files, start, end, d = read_file_entries(path)
    data, block = read_data_entries(path)
    print("header block            : %d bytes" % len(d))
    if start is None:
        print("file entry array        : ABSENT -- Offset0 == Offset1, so the")
        print("                          file-data area is zero bytes long and")
        print("                          this installer has no payload.")
        print("data entries            : %d" % len(data))
        return
    print("file entry array starts : %d" % start)
    print("file entry array ends   : %d" % end)
    print("file entries            : %d" % len(files))
    print("data entries            : %d" % len(data))
    print("locations are 0..N-1    : %s"
          % all(e["location"] == i for i, e in enumerate(files)))
    print("every location in range : %s"
          % all(e["location"] < len(data) for e in files))
    print("data entries unreferenced: %d"
          % (len(data) - len(set(e["location"] for e in files))))
    strides = set(e["end"] - e["start"] - len(e["dest"]) for e in files)
    print("fixed part of the record: %s" % sorted(strides))
    chunks = {}
    for r in data:
        chunks.setdefault((r["start_offset"], r["chunk_compressed_size"]), 0)
        chunks[(r["start_offset"], r["chunk_compressed_size"])] += 1
    print("distinct chunks         : %d" % len(chunks))
    for (so, cs), n in sorted(chunks.items()):
        print("   start_offset %12d  compressed %12d  %d files" % (so, cs, n))
    total = sum(r["original_size"] for r in data)
    print("sum of OriginalSize     : %d" % total)


def cmd_flags(path):
    """Census of the 16-bit Flags field on the data entries.

    Two of these bits carry the session's weight. `TimeStampInUTC` is what
    settles the timezone question in docs/07, and `CallInstructionOptimized`
    is what accounts for the 22 checksum failures in docs/05 -- the count
    printed here must equal the count of MD5 mismatches from --extract, and
    does."""
    import collections
    data, _ = read_data_entries(path)
    c = collections.Counter(r["flags"] for r in data)
    print("data entries : %d" % len(data))
    for v, n in c.most_common():
        bits = [DATA_FLAG_NAMES[i] for i in range(len(DATA_FLAG_NAMES))
                if v >> i & 1]
        print("  0x%04X  x%-6d %s" % (v, n, ", ".join(bits)))
    print()
    for i, name in enumerate(DATA_FLAG_NAMES):
        n = sum(1 for r in data if r["flags"] >> i & 1)
        if n:
            print("  %-28s %6d of %d" % (name, n, len(data)))


def cmd_files(path):
    files, data = joined(path)
    print("%12s  %-19s  %5s  %s" % ("bytes", "source timestamp", "loc", "destination"))
    for e in files:
        r = e["data"]
        print("%12d  %-19s  %5d  %s" % (
            r["original_size"] if r else -1,
            filetime_to_iso(r["filetime"]) if r else "?",
            e["location"], e["dest"]))


def cmd_census(path):
    import collections
    files, data = joined(path)
    total = sum(e["data"]["original_size"] for e in files if e["data"])
    print("files                   : %d" % len(files))
    print("total uncompressed bytes: %d" % total)
    print()
    for key, title in ((lambda e: _topdir(e["dest"]), "top-level directory"),
                       (lambda e: _ext(e["dest"]), "extension")):
        cnt = collections.Counter()
        siz = collections.Counter()
        for e in files:
            cnt[key(e)] += 1
            siz[key(e)] += e["data"]["original_size"] if e["data"] else 0
        print("=== by %s ===" % title)
        print("%-34s %7s %14s %8s" % ("", "files", "bytes", "% bytes"))
        for k, _ in siz.most_common():
            print("%-34s %7d %14d %7.3f%%"
                  % (k, cnt[k], siz[k], 100.0 * siz[k] / total))
        print()


def _topdir(p):
    parts = p.split(chr(92))
    return parts[0] if len(parts) == 1 else chr(92).join(parts[:2])


def _ext(p):
    b = p.split(chr(92))[-1]
    return ("." + b.rsplit(".", 1)[1].lower()) if "." in b else "(none)"


def cmd_extract(path, outdir, only=None):
    """Single pass over the solid stream.

    The payload is one LZMA1 chunk introduced by `zlb\\x1a`; every file is a
    byte range inside it given by ChunkSuboffset and OriginalSize. Because the
    ranges are in increasing order, nothing has to be held in memory: the
    stream is decompressed incrementally and each file is written as its range
    goes past. A 1.2 GB payload therefore costs a few megabytes of RAM."""
    import hashlib
    t = read_offset_table(path)
    files, data = joined(path)
    order = sorted((e for e in files if e["data"]),
                   key=lambda e: (e["data"]["start_offset"],
                                  e["data"]["chunk_suboffset"]))
    if only:
        order = [e for e in order if e["dest"].startswith(only)]
    groups = {}
    for e in order:
        groups.setdefault(e["data"]["start_offset"], []).append(e)
    written = 0
    bad_md5 = []
    f = open(path, "rb")
    for start_offset in sorted(groups):
        base = t["offset1"] + start_offset
        f.seek(base)
        magic = f.read(4)
        if magic != b"zlb\x1a":
            raise InnoError("chunk at %d does not start with zlb: %r"
                            % (base, magic))
        props = f.read(5)
        dec = lzma.LZMADecompressor(format=lzma.FORMAT_ALONE)
        primed = props + b"\xff" * 8
        pos = 0
        pending = list(groups[start_offset])
        buf = bytearray()
        buf += dec.decompress(primed)
        want = pending[0]["data"]["chunk_suboffset"] if pending else 0
        while pending:
            raw = f.read(1 << 20)
            if not raw:
                break
            buf += dec.decompress(raw)
            while pending:
                e = pending[0]
                r = e["data"]
                a = r["chunk_suboffset"] - pos
                b = a + r["original_size"]
                if b > len(buf):
                    break
                blob = bytes(buf[a:b])
                dst = os.path.join(outdir, _clean(e["dest"]))
                d = os.path.dirname(dst)
                if d and not os.path.isdir(d):
                    os.makedirs(d)
                with open(dst, "wb") as g:
                    g.write(blob)
                if hashlib.md5(blob).digest() != r["md5"]:
                    bad_md5.append(e["dest"])
                written += 1
                pending.pop(0)
            if pending:
                keep = pending[0]["data"]["chunk_suboffset"] - pos
                if keep > 0:
                    del buf[:keep]
                    pos += keep
    f.close()
    print("files written : %d" % written)
    print("MD5 mismatches: %d" % len(bad_md5))
    for n in bad_md5[:20]:
        print("   %s" % n)


def _clean(dest):
    p = dest
    if p.startswith("{"):
        p = p.split("}", 1)[1]
    return p.lstrip(chr(92)).replace(chr(92), "/")


def main():
    if len(sys.argv) < 3:
        print(__doc__)
        return 2
    path = sys.argv[1]
    mode = sys.argv[2]
    if mode == "--ldr":
        cmd_ldr(path)
    elif mode == "--blocks":
        cmd_blocks(path)
    elif mode == "--header":
        save = None
        if "--save" in sys.argv:
            save = sys.argv[sys.argv.index("--save") + 1]
        cmd_header(path, save)
    elif mode == "--strings":
        minlen = 4
        if "--min" in sys.argv:
            minlen = int(sys.argv[sys.argv.index("--min") + 1])
        cmd_strings(path, minlen)
    elif mode == "--check-lzma":
        cmd_check_lzma(path)
    elif mode == "--verify-entries":
        cmd_verify_entries(path)
    elif mode == "--flags":
        cmd_flags(path)
    elif mode == "--files":
        cmd_files(path)
    elif mode == "--census":
        cmd_census(path)
    elif mode == "--extract":
        only = None
        if "--only" in sys.argv:
            only = sys.argv[sys.argv.index("--only") + 1]
        cmd_extract(path, sys.argv[3], only)
    else:
        print(__doc__)
        return 2
    return 0


if __name__ == "__main__":
    sys.exit(main())
