#!/usr/bin/env python3
"""director.py -- read Macromedia Director movies and projector overlays.

The centrepiece of this disc is a Director 7 projector, `883.exe`, plus three
`.dxr` movies. No previous disc in this collection contained a Director file,
so this is a new reader written from the container up.

WHAT THE CONTAINER IS

A Director movie is RIFX -- IFF/RIFF with big-endian lengths. On Windows the
whole file is byte-swapped instead, which produces a file whose first four
bytes read `XFIR` rather than `RIFX`, whose lengths are little-endian, and --
this is the part that costs you an afternoon -- **whose four-character chunk
tags are themselves byte-reversed**. `imap` is stored as `pami`. `mmap` is
stored as `pamm`. `CASt` is stored as `tSAC`. The codec after the outer length
reads `39VM`, which is `MV93` reversed, which is Director's own version tag.

So the first decision the reader makes is endianness, and it makes it from the
first four bytes, and then it applies the same swap to every tag it reads.

That is only half the rule, and the other half cost four separate bugs before
it was written down properly:

    the XFIR byte-swap applies to the chunk FRAMING ONLY -- the four-character
    tags, and the lengths and offsets inside imap and mmap. Every chunk BODY
    stays big-endian.

Reading a body little-endian does not crash. It yields plausible positive
integers: 65535 handlers, 17152 names, cast type 16777216, a text length of
301989888. Each of those is 0x0100-something with the bytes reversed, and each
one looked like a number until it was checked against something else. The four
occasions, and what falsified each, are in `docs/22-tools.md`.

HOW YOU FIND THE CHUNKS

Not by scanning. `imap` sits immediately after the 12-byte outer header and
contains the file offset of `mmap`. `mmap` is the memory map: a header giving
entry count and entry stride, then one 20-byte entry per chunk, each entry
carrying a tag, a length, a file offset and a flags word. Everything else in
the file is addressed through those entries. A scanning reader would find
`snd ` inside compressed bitmap data and invent chunks; this reader never
searches.

WHAT IT REPORTS

  --map        the mmap: every chunk with tag, offset, length, and the bytes
               each tag accounts for, which is how you learn that a 15 MB
               movie is 60 % bitmaps
  --cast       the cast: KEY* associates cast member chunks with their data
               chunks, CAS* gives the member order, CASt gives each member's
               type. Prints a census by type.
  --names      the Lnam chunk: Director's name table, in plain text. On a
               protected movie this is the only place handler and property
               names survive, and it is the single most informative chunk in
               a `.dxr`.
  --scripts    Lscr chunk census: per script, the byte size, the handler count
               and the literal pool, printed as text.
  --text       STXT chunks: the text cast members, verbatim.
  --overlay    for a projector .exe: locate the appended movie and parse it.

WHAT IT DOES NOT DO

It does not decompile Lingo bytecode into Lingo. It reports handler names,
literal strings and sizes. That is a census, not a decompilation, and the
distinction is deliberate: a census is checkable by anyone with the file.

    python tools/director.py FILE --map
    python tools/director.py FILE --cast
    python tools/director.py FILE --names
    python tools/director.py FILE --scripts
    python tools/director.py FILE --text
    python tools/director.py PROJECTOR.exe --overlay --map
"""
import argparse
import os
import struct
import sys
from collections import Counter, defaultdict

# Director cast member types. Values 1..11 are stable across D4..D8; 12..16 are
# what D6/D7 added. Anything outside the table is printed as its number rather
# than guessed at.
CAST_TYPES = {
    0: "null",
    1: "bitmap",
    2: "filmLoop",
    3: "field",
    4: "palette",
    5: "picture",
    6: "sound",
    7: "button",
    8: "shape",
    9: "movie",
    10: "digitalVideo",
    11: "script",
    12: "richText",
    13: "ole",
    14: "transition",
    15: "xtra",
    16: "sound(x)",
}

SCRIPT_TYPES = {1: "score/behavior", 2: "movie", 3: "parent"}


class Reader(object):
    """A Director RIFX/XFIR file, addressed through its own memory map."""

    def __init__(self, data, base=0):
        self.data = data
        self.base = base
        magic = data[base:base + 4]
        if magic == b"XFIR":
            self.little = True
        elif magic == b"RIFX":
            self.little = False
        else:
            raise ValueError("not a Director container: magic %r at offset %d"
                             % (magic, base))
        self.end = "<" if self.little else ">"
        # BUG #1, and it cost an hour. The XFIR byte-swap applies to the chunk
        # FRAMING -- the four-character tags and the 32-bit lengths in imap and
        # mmap -- and NOT to the contents of every chunk. The Lingo family
        # (Lnam, Lscr, Lctx) keeps its original big-endian layout inside a
        # little-endian container. Read Lnam's header little-endian and the
        # name count comes out as 17152 (0x4300) and 52480 (0xCD00), which are
        # 67 and 205 with the bytes the other way round. Both wrong values are
        # plausible-looking positive integers, which is why the first version
        # printed "0 of 17152 names read" instead of crashing.
        self.lend = ">"
        self.riff_len = self.u32(base + 4)
        self.codec = self.tag(base + 8)
        self.chunks = []          # list of dicts
        self.by_id = {}
        self._read_imap_mmap()

    # ---- primitives -------------------------------------------------------

    def u32(self, off):
        return struct.unpack_from(self.end + "I", self.data, off)[0]

    def i32(self, off):
        return struct.unpack_from(self.end + "i", self.data, off)[0]

    def u16(self, off):
        return struct.unpack_from(self.end + "H", self.data, off)[0]

    def tag(self, off):
        """Read a four-character tag, undoing the byte reversal if little."""
        raw = self.data[off:off + 4]
        return raw[::-1] if self.little else raw

    # ---- the map ----------------------------------------------------------

    def _read_imap_mmap(self):
        off = self.base + 12
        t = self.tag(off)
        if t != b"imap":
            raise ValueError("expected imap at offset %d, found %r" % (off, t))
        imap_len = self.u32(off + 4)
        body = off + 8
        # imap body: u32 mmapCount, u32 mmapOffset, u32 fileVersion, ...
        self.imap_count = self.u32(body)
        mmap_off = self.u32(body + 4)
        self.file_version = self.u32(body + 8) if imap_len >= 12 else None
        mmap_off += self.base if self.base and mmap_off < self.base else 0

        t = self.tag(mmap_off)
        if t != b"mmap":
            raise ValueError("expected mmap at offset %d (from imap), found %r"
                             % (mmap_off, t))
        self.mmap_offset = mmap_off
        b = mmap_off + 8
        self.mmap_props_size = self.u16(b)
        self.mmap_entry_size = self.u16(b + 2)
        self.mmap_max = self.i32(b + 4)
        self.mmap_used = self.i32(b + 8)
        self.junk_head = self.i32(b + 12)
        self.junk_head2 = self.i32(b + 16)
        self.free_head = self.i32(b + 20)
        entries = b + self.mmap_props_size
        stride = self.mmap_entry_size
        for i in range(self.mmap_used):
            e = entries + i * stride
            if e + stride > len(self.data):
                break
            tag = self.tag(e)
            length = self.u32(e + 4)
            offset = self.u32(e + 8)
            flags = self.u16(e + 12)
            unk = self.u16(e + 14)
            link = self.i32(e + 16) if stride >= 20 else 0
            if self.base and offset and offset < self.base:
                offset += self.base
            c = {"id": i, "tag": tag, "len": length, "off": offset,
                 "flags": flags, "unk": unk, "link": link}
            self.chunks.append(c)
            self.by_id[i] = c

    def body(self, c):
        """Bytes of a chunk, excluding its 8-byte header."""
        if c["tag"] in (b"free", b"junk") or c["off"] == 0:
            return b""
        return self.data[c["off"] + 8:c["off"] + 8 + c["len"]]

    def find(self, tag):
        return [c for c in self.chunks if c["tag"] == tag]

    # ---- Lnam: the name table --------------------------------------------

    def names(self):
        out = []
        for c in self.find(b"Lnam"):
            d = self.body(c)
            if len(d) < 20:
                continue
            names_off = struct.unpack_from(self.lend + "H", d, 16)[0]
            count = struct.unpack_from(self.lend + "H", d, 18)[0]
            p = names_off
            got = []
            for _ in range(count):
                if p >= len(d):
                    break
                n = d[p]
                got.append(d[p + 1:p + 1 + n])
                p += 1 + n
            out.append((c["id"], count, got))
        return out

    # ---- Lscr: script bytecode + literal pool -----------------------------

    def scripts(self):
        """Return per-Lscr: (id, size, handler count, literal strings)."""
        out = []
        for c in self.find(b"Lscr"):
            d = self.body(c)
            info = {"id": c["id"], "size": len(d), "handlers": None,
                    "literals": [], "script_type": None, "parse_error": None,
                    "properties": None, "globals": None, "lit_count": 0,
                    "lit_data_bytes": 0, "consistent": None, "header_len": None}
            try:
                # BUG #2. The first version put the handler and literal counts
                # at 0x30, 0x3A, 0x3C and 0x44. Every script then reported
                # 65535 handlers, because 0x30 is factoryNameID and an ordinary
                # non-factory script stores -1 there. 65535 is a number and not
                # a crash, so the tool printed a total of 5,767,080 handlers
                # across 88 scripts and looked like it was working.
                #
                # The real Director 5+ Lscr header, offsets from the start of
                # the chunk body, every field big-endian (see BUG #1):
                #
                #   0x08 u32 totalLength          0x10 u16 headerLength (0x5C)
                #   0x12 u16 scriptNumber         0x2C i32 castID
                #   0x30 i16 factoryNameID        0x32 u16 handlerVectorsCount
                #   0x34 u32 handlerVectorsOffset 0x38 u32 handlerVectorsSize
                #   0x3C u16 propertiesCount      0x3E u32 propertiesOffset
                #   0x42 u16 globalsCount         0x44 u32 globalsOffset
                #   0x48 u16 handlersCount        0x4A u32 handlersOffset
                #   0x4E u16 literalsCount        0x50 u32 literalsOffset
                #   0x54 u32 literalsDataCount    0x58 u32 literalsDataOffset
                #
                # The check that proves the reading, rather than making it look
                # plausible: literalsOffset + 8*literalsCount must equal
                # literalsDataOffset exactly, because the literal table is 8
                # bytes per entry and the string data follows immediately. On
                # Lscr 3606 that is 1360 + 8*321 = 3928, which is exactly what
                # 0x58 holds. Three fields agreeing is a parse. Two fields
                # that look reasonable is a guess.
                be = self.lend
                info["header_len"] = struct.unpack_from(be + "H", d, 0x10)[0]
                info["script_type"] = struct.unpack_from(be + "H", d, 0x12)[0]
                pcount = struct.unpack_from(be + "H", d, 0x3C)[0]
                gcount = struct.unpack_from(be + "H", d, 0x42)[0]
                hcount = struct.unpack_from(be + "H", d, 0x48)[0]
                lcount = struct.unpack_from(be + "H", d, 0x4E)[0]
                ltab = struct.unpack_from(be + "I", d, 0x50)[0]
                ldlen = struct.unpack_from(be + "I", d, 0x54)[0]
                ldata = struct.unpack_from(be + "I", d, 0x58)[0]
                info["handlers"] = hcount
                info["properties"] = pcount
                info["globals"] = gcount
                info["lit_count"] = lcount
                info["lit_data_bytes"] = ldlen
                info["consistent"] = (ltab + 8 * lcount == ldata)
                lits = []
                for i in range(min(lcount, 8192)):
                    e = ltab + i * 8
                    if e + 8 > len(d):
                        break
                    ltype = struct.unpack_from(be + "I", d, e)[0]
                    loff = struct.unpack_from(be + "I", d, e + 4)[0]
                    if ltype != 1:        # 1 = string, 4 = integer, 9 = float
                        continue
                    q = ldata + loff
                    if q + 4 > len(d):
                        continue
                    n = struct.unpack_from(be + "I", d, q)[0]
                    if 0 < n <= 8192 and q + 4 + n <= len(d):
                        lits.append(d[q + 4:q + 4 + n].rstrip(b"\x00"))
                info["literals"] = lits
            except (struct.error, IndexError) as exc:
                info["parse_error"] = str(exc)
            out.append(info)
        return out

    # ---- STXT: text cast member contents ---------------------------------

    def texts(self):
        out = []
        for c in self.find(b"STXT"):
            d = self.body(c)
            if len(d) < 12:
                continue
            # BUG #1 for the fourth and last time: STXT bodies are big-endian
            # too. Little-endian gave text lengths of 301989888 (0x12000000)
            # and 33554432 (0x02000000), which are 18 and 2 -- "INSTALLA
            # QUICKTIME" is 18 characters and "Si" is 2.
            offset = struct.unpack_from(self.lend + "I", d, 0)[0]
            tlen = struct.unpack_from(self.lend + "I", d, 4)[0]
            if offset + tlen <= len(d):
                out.append((c["id"], tlen, d[offset:offset + tlen]))
            else:
                out.append((c["id"], tlen, d[12:12 + min(tlen, len(d) - 12)]))
        return out

    # ---- KEY* / CAS* / CASt: the cast ------------------------------------

    def keytable(self):
        """KEY*: (owner chunk id, child chunk id, tag) triples."""
        out = []
        for c in self.find(b"KEY*"):
            d = self.body(c)
            # KEY* is framing-adjacent but still a chunk body: big-endian.
            props = struct.unpack_from(self.lend + "H", d, 0)[0]
            stride = struct.unpack_from(self.lend + "H", d, 2)[0]
            used = struct.unpack_from(self.lend + "i", d, 8)[0]
            for i in range(used):
                e = props + i * stride
                if e + stride > len(d):
                    break
                child = struct.unpack_from(self.lend + "i", d, e)[0]
                owner = struct.unpack_from(self.lend + "i", d, e + 4)[0]
                raw = d[e + 8:e + 12]
                tag = raw
                out.append((owner, child, tag))
        return out

    def cast_arrays(self):
        """CAS*: ordered lists of cast member chunk ids."""
        out = []
        for c in self.find(b"CAS*"):
            d = self.body(c)
            n = len(d) // 4
            ids = list(struct.unpack_from(self.lend + "%di" % n, d, 0))
            out.append((c["id"], ids))
        return out

    def cast_members(self):
        """CASt: (chunk id, type code, name) per member."""
        out = []
        for c in self.find(b"CASt"):
            d = self.body(c)
            if len(d) < 12:
                continue
            # BUG #3, and it is BUG #1 again in a new place. Read little-endian
            # inside an XFIR file and the cast types come out as 16777216,
            # 184549376, 251658240 -- which are 0x01000000, 0x0B000000 and
            # 0x0F000000, i.e. 1, 11 and 15 with the bytes the other way round.
            # Bitmap, script and Xtra. So CASt bodies are big-endian too, and
            # the working rule for this container is:
            #
            #   the XFIR byte-swap applies to the chunk FRAMING ONLY -- the
            #   four-character tags, and the lengths and offsets in imap and
            #   mmap. Every chunk BODY stays big-endian.
            #
            # The check that this is right and not merely plausible: with the
            # big-endian reading, the number of type-1 (bitmap) cast members
            # equals the number of BITD chunks in the same file, and the number
            # of type-6 (sound) members equals the number of sndS chunks --
            # exactly, in all three movies and both projector overlays. Two
            # independent chunk censuses agreeing is a parse.
            ctype = struct.unpack_from(self.lend + "I", d, 0)[0]
            info_len = struct.unpack_from(self.lend + "I", d, 4)[0]
            spec_len = struct.unpack_from(self.lend + "I", d, 8)[0]
            name = b""
            # The cast-info block follows the 12-byte header. It is itself a
            # little list-of-offsets structure; the member name is the second
            # entry. Parsed defensively: a wrong name is worse than no name.
            try:
                info = d[12:12 + info_len]
                if len(info) >= 20:
                    hdr = struct.unpack_from(self.lend + "I", info, 0)[0]
                    cnt = struct.unpack_from(self.lend + "H", info, 16)[0]
                    offs_at = 18
                    offs = [struct.unpack_from(self.lend + "I", info, offs_at + 4 * i)[0]
                            for i in range(min(cnt + 1, 24))
                            if offs_at + 4 * i + 4 <= len(info)]
                    if len(offs) >= 3:
                        base = offs_at + 4 * (cnt + 1)
                        s, e = base + offs[1], base + offs[2]
                        if 0 <= s < e <= len(info):
                            raw = info[s:e]
                            if raw and raw[0] == len(raw) - 1:
                                raw = raw[1:]
                            name = raw
            except (struct.error, IndexError):
                name = b""
            out.append((c["id"], ctype, info_len, spec_len, name))
        return out


# ---------------------------------------------------------------------------
# projector overlays
# ---------------------------------------------------------------------------

def find_overlays(data):
    """Every offset where a Director container header begins.

    A projector .exe is a PE whose sections are the Director runtime and whose
    overlay is one or more embedded movies. The offsets are found by looking
    for the container magic followed by a plausible codec tag -- not by
    scanning for the magic alone, which hits inside compressed data.
    """
    hits = []
    for magic, codec_ok in ((b"XFIR", (b"39VM", b"NUJA", b"57VM")),
                            (b"RIFX", (b"MV93", b"AJUN", b"MV57"))):
        start = 0
        while True:
            i = data.find(magic, start)
            if i < 0:
                break
            start = i + 1
            if data[i + 8:i + 12] in codec_ok:
                hits.append((i, magic, data[i + 8:i + 12]))
    hits.sort()
    return hits


# ---------------------------------------------------------------------------
# reporting
# ---------------------------------------------------------------------------

def report_header(r, path, base):
    print("file            : %s" % path)
    print("container at    : offset %d" % base)
    print("magic           : %s  (%s-endian lengths, tags %s)"
          % ("XFIR" if r.little else "RIFX",
             "little" if r.little else "big",
             "byte-reversed" if r.little else "as written"))
    print("declared length : %d  (file has %d bytes from that offset)"
          % (r.riff_len, len(r.data) - base))
    print("codec tag       : %s" % r.codec.decode("latin-1"))
    print("imap entries    : %d   file version field: %s"
          % (r.imap_count, r.file_version))
    print("mmap at         : offset %d" % r.mmap_offset)
    print("mmap props/entry: %d / %d bytes" % (r.mmap_props_size, r.mmap_entry_size))
    print("mmap used/max   : %d / %d" % (r.mmap_used, r.mmap_max))


def do_map(r):
    print()
    print("=== chunk census by tag ===")
    # mmap entry 0 is the outer RIFX container itself, whose declared length is
    # the whole file. Counting it in the census double-counts every byte and
    # pins every real tag's share at half of what it is. It is reported on its
    # own line and excluded from the total.
    real = [c for c in r.chunks if c["id"] != 0]
    per = defaultdict(lambda: [0, 0])
    for c in real:
        per[c["tag"]][0] += 1
        per[c["tag"]][1] += c["len"]
    total = sum(v[1] for v in per.values())
    print("%-8s %7s %14s %8s" % ("tag", "count", "bytes", "share"))
    print("-" * 8 + " " + "-" * 7 + " " + "-" * 14 + " " + "-" * 8)
    for tag, (n, b) in sorted(per.items(), key=lambda kv: -kv[1][1]):
        name = tag.decode("latin-1")
        print("%-8s %7d %14d %7.2f%%"
              % (name, n, b, 100.0 * b / total if total else 0))
    print("-" * 8 + " " + "-" * 7 + " " + "-" * 14 + " " + "-" * 8)
    print("%-8s %7d %14d %7.2f%%" % ("TOTAL", len(real), total, 100.0))
    print()
    print("entry 0 (the outer container) declares %d bytes and is excluded above."
          % r.chunks[0]["len"])
    freed = sum(1 for c in real if c["tag"] in (b"free", b"junk"))
    print("free/junk entries : %d of %d (%.1f%% of the map is dead space)"
          % (freed, len(real), 100.0 * freed / len(real) if real else 0))
    accounted = total + 8 * len([c for c in real if c["len"]])
    print("chunk bytes + headers: %d of %d file bytes (%.2f%%)"
          % (accounted, len(r.data) - r.base,
             100.0 * accounted / (len(r.data) - r.base)))


def do_chunks(r):
    print()
    print("%-6s %-8s %12s %12s %6s" % ("id", "tag", "offset", "length", "flags"))
    for c in r.chunks:
        print("%-6d %-8s %12d %12d %6d"
              % (c["id"], c["tag"].decode("latin-1"), c["off"], c["len"], c["flags"]))


def do_cast(r):
    print()
    members = r.cast_members()
    print("=== cast members (CASt chunks: %d) ===" % len(members))
    per = Counter(m[1] for m in members)
    print("%-16s %7s" % ("type", "count"))
    for t, n in sorted(per.items(), key=lambda kv: -kv[1]):
        print("%-16s %7d" % (CAST_TYPES.get(t, "type %d" % t), n))
    print()
    print("cross-check against the chunk census (these must be equal):")
    for tname, code, chunk in (("bitmap", 1, b"BITD"), ("sound", 6, b"sndS"),
                               ("palette", 4, b"CLUT")):
        a = per.get(code, 0)
        b = len(r.find(chunk))
        print("    %-8s cast members %-5d vs %s chunks %-5d   %s"
              % (tname, a, chunk.decode("latin-1"), b,
                 "agree" if a == b else "DISAGREE"))
    print()
    arrays = r.cast_arrays()
    for cid, ids in arrays:
        nonzero = [i for i in ids if i > 0]
        print("CAS* chunk %d: %d slots, %d filled, ids %d..%d"
              % (cid, len(ids), len(nonzero),
                 min(nonzero) if nonzero else 0, max(nonzero) if nonzero else 0))
    keys = r.keytable()
    if keys:
        print()
        print("KEY* associations: %d" % len(keys))
        per = Counter(t for _, _, t in keys)
        for t, n in per.most_common():
            print("    %-8s %d" % (t.decode("latin-1"), n))
    named = [m for m in members if m[4]]
    if named:
        print()
        print("named cast members: %d of %d" % (len(named), len(members)))
        for cid, t, il, sl, name in named[:400]:
            print("    %-6d %-14s %r" % (cid, CAST_TYPES.get(t, str(t)), name))


def do_names(r):
    print()
    tables = r.names()
    if not tables:
        print("no Lnam chunk in this file")
        return
    for cid, count, got in tables:
        print("=== Lnam chunk %d: %d names ===" % (cid, count))
        for i, n in enumerate(got):
            print("%5d  %s" % (i, n.decode("latin-1")))
        print()
        print("names read: %d of %d declared" % (len(got), count))


def do_scripts(r, dump_literals=True):
    print()
    scripts = r.scripts()
    print("=== Lscr chunks: %d ===" % len(scripts))
    if not scripts:
        return
    tot = sum(s["size"] for s in scripts)
    hs = [s["handlers"] for s in scripts if s["handlers"] is not None]
    print("total bytecode bytes : %d" % tot)
    print("handlers, total      : %d" % sum(hs))
    print("largest script       : %d bytes" % max(s["size"] for s in scripts))
    errs = [s for s in scripts if s["parse_error"]]
    if errs:
        print("scripts that failed to parse: %d" % len(errs))
    print()
    ok = sum(1 for s in scripts if s["consistent"])
    print("literal tables self-consistent (off + 8*count == dataOff): %d of %d"
          % (ok, len(scripts)))
    print("string-literal data bytes : %d"
          % sum(s["lit_data_bytes"] for s in scripts))
    print()
    print("%-6s %9s %6s %6s %6s %9s %8s"
          % ("id", "bytes", "hndlr", "props", "globs", "literals", "strings"))
    for s in scripts:
        print("%-6d %9d %6s %6s %6s %9d %8d"
              % (s["id"], s["size"],
                 "?" if s["handlers"] is None else s["handlers"],
                 "?" if s["properties"] is None else s["properties"],
                 "?" if s["globals"] is None else s["globals"],
                 s["lit_count"], len(s["literals"])))
    if dump_literals:
        print()
        print("=== literal pools ===")
        for s in scripts:
            if not s["literals"]:
                continue
            print("--- Lscr %d (%d literals)" % (s["id"], len(s["literals"])))
            for lit in s["literals"]:
                print("    %s" % lit.decode("latin-1"))


def do_text(r):
    print()
    texts = r.texts()
    print("=== STXT chunks: %d ===" % len(texts))
    for cid, tlen, raw in texts:
        print("--- STXT %d (%d bytes)" % (cid, tlen))
        print(raw.decode("latin-1"))
        print()


def main():
    # notes/*.txt has to survive a byte the console cannot encode. Director
    # literal pools here are CP1252 and MacRoman Italian, and one stray 0x86
    # killed an entire run mid-file, leaving a truncated saved note.
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass
    ap = argparse.ArgumentParser()
    ap.add_argument("file")
    ap.add_argument("--map", action="store_true")
    ap.add_argument("--chunks", action="store_true")
    ap.add_argument("--cast", action="store_true")
    ap.add_argument("--names", action="store_true")
    ap.add_argument("--scripts", action="store_true")
    ap.add_argument("--text", action="store_true")
    ap.add_argument("--overlay", action="store_true")
    ap.add_argument("--which", type=int, default=0,
                    help="with --overlay, which embedded container to open")
    args = ap.parse_args()

    data = open(args.file, "rb").read()

    if args.overlay:
        hits = find_overlays(data)
        print("embedded Director containers found: %d" % len(hits))
        for i, (off, magic, codec) in enumerate(hits):
            print("    [%d] offset %-12d magic %s codec %s"
                  % (i, off, magic.decode("latin-1"), codec.decode("latin-1")))
        if not hits:
            return
        base = hits[args.which][0]
        print()
    else:
        base = 0

    try:
        r = Reader(data, base)
    except ValueError as exc:
        print("cannot open: %s" % exc)
        return 1

    report_header(r, args.file, base)
    if args.map:
        do_map(r)
    if args.chunks:
        do_chunks(r)
    if args.cast:
        do_cast(r)
    if args.names:
        do_names(r)
    if args.scripts:
        do_scripts(r)
    if args.text:
        do_text(r)
    if not any([args.map, args.chunks, args.cast, args.names,
                args.scripts, args.text]):
        do_map(r)
    return 0


if __name__ == "__main__":
    sys.exit(main() or 0)
