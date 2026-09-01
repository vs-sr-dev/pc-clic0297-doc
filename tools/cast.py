#!/usr/bin/env python3
r"""cast.py - recover the character table out of gf.exe.

The game's cast is not in a data file and it is not a pointer array either:
the first attempt at this tool looked for a static table of pointers, found
the anchor's only reference inside `.text` as an instruction operand, and had
to be rewritten. The strings are pushed one at a time by code, so what exists
in the data section is the *literal pool*, in the order the compiler emitted
it, and that order is the record order.

So the method is: index every NUL-terminated string in `.data` by address,
sort by address, and cut the run into records at the places where a string is
immediately followed by a `chars\<something>\` texture path. That path is the
one field every character has and nothing else has.

A record turns out to be:

    display name
    chars\<dir>\                one to three of these
    surname
    birthplace and date of birth
    town of residence           not always present
    star sign                   not always present
    occupation
    distinguishing marks        zero to two lines

Only the first three positions are fixed; the tail varies in length from
character to character, so this tool prints the fields it finds rather than
forcing them into columns it has decided on in advance.

Usage:
    python tools/cast.py gf.exe
    python tools/cast.py gf.exe --names-only
    python tools/cast.py gf.exe --anchor 'chars\pietro\'
"""

import argparse
import re
import struct

STRING_RE = re.compile(rb"[\x20-\x7e]{2,}\x00")
BS = chr(92)
PATH_RE = re.compile(re.escape("chars" + BS) + r"[A-Za-z0-9_" + re.escape(BS)
                     + r"]+" + re.escape(BS) + r"$")
EDITION_RE = re.compile(r"^(.*?)\s+([123])a$")


def sections(d):
    e_lfanew = struct.unpack_from("<I", d, 0x3C)[0]
    nsec = struct.unpack_from("<H", d, e_lfanew + 6)[0]
    optsize = struct.unpack_from("<H", d, e_lfanew + 20)[0]
    base = struct.unpack_from("<I", d, e_lfanew + 24 + 28)[0]
    off = e_lfanew + 24 + optsize
    out = []
    for i in range(nsec):
        h = d[off + 40 * i:off + 40 * (i + 1)]
        name = h[:8].rstrip(b"\x00").decode("ascii", "replace")
        vsize, vaddr, rsize, raddr = struct.unpack_from("<IIII", h, 8)
        out.append((name, vaddr, vsize, raddr, rsize))
    return base, out


def literal_pool(d, base, secs, want=".data"):
    """Every printable NUL-terminated string in one section, in address
    order, as (virtual address, text)."""
    out = []
    for name, vaddr, vsize, raddr, rsize in secs:
        if name != want:
            continue
        blob = d[raddr:raddr + rsize]
        for m in STRING_RE.finditer(blob):
            va = base + vaddr + m.start()
            out.append((va, m.group()[:-1].decode("cp1252", "replace")))
    out.sort()
    return out


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("exe")
    ap.add_argument("--section", default=".data")
    ap.add_argument("--anchor", default="chars" + BS + "pietro" + BS)
    ap.add_argument("--names-only", action="store_true")
    a = ap.parse_args()

    with open(a.exe, "rb") as fh:
        d = fh.read()
    base, secs = sections(d)
    pool = literal_pool(d, base, secs, a.section)

    print("image base 0x%08X, section %s, %d strings in the literal pool"
          % (base, a.section, len(pool)))

    idx = [i for i, (va, s) in enumerate(pool) if s == a.anchor]
    if len(idx) != 1:
        print("anchor %r appears %d times; refusing to guess"
              % (a.anchor, len(idx)))
        return
    print("anchor %r at pool index %d, VA 0x%08X"
          % (a.anchor, idx[0], pool[idx[0]][0]))

    is_path = [bool(PATH_RE.match(s)) for va, s in pool]
    print("strings matching %r: %d"
          % ("chars" + BS + "...", sum(is_path)))

    # A record begins at the string immediately before a run of paths, unless
    # that string is itself a path.
    starts = []
    for i in range(len(pool) - 1):
        if is_path[i + 1] and not is_path[i]:
            starts.append(i)
    print("record starts found: %d" % len(starts))
    if not starts:
        return

    lo, hi = starts[0], starts[-1]
    print("cast region: pool index %d .. end of last record, VA 0x%08X..0x%08X"
          % (lo, pool[lo][0], pool[hi][0]))

    # The literal pool holds other things after the cast. Real cast records
    # sit 0x30..0x90 bytes apart; the first big gap ends the table.
    GAP = 512
    cut = len(starts)
    for j in range(1, len(starts)):
        if pool[starts[j]][0] - pool[starts[j - 1]][0] > GAP:
            cut = j
            break
    if cut < len(starts):
        print("address gap > %d bytes after record %d: table ends there"
              % (GAP, cut - 1))
    starts = starts[:cut]

    records = []
    for j, s in enumerate(starts):
        e = starts[j + 1] if j + 1 < len(starts) else len(pool)
        # the last record has no following start to bound it, so bound it the
        # same way the table itself was bounded: by the first address gap that
        # is bigger than any gap inside a record
        # The last record has no following start to bound it. Biography
        # fields are prose; what follows the table is resource paths. So the
        # record ends at the first string that contains a backslash and is
        # not one of this character's own chars\ paths.
        fields = []
        for va, t in pool[s:e]:
            if fields and BS in t and not PATH_RE.match(t):
                break
            fields.append(t)
        # a record ends where the next thing that is clearly not biography
        # begins; the last record is trimmed at the first path-looking
        # string that is not a chars path
        records.append((pool[s][0], fields))

    print()
    print("=" * 78)
    print("CAST")
    print("=" * 78)
    total_paths = 0
    editions = {}
    for j, (va, f) in enumerate(records):
        name = f[0]
        paths = [x for x in f if PATH_RE.match(x)]
        total_paths += len(paths)
        rest = [x for x in f[1:] if not PATH_RE.match(x)]
        m = EDITION_RE.match(name)
        if m:
            editions[m.group(2)] = editions.get(m.group(2), 0) + 1
        if a.names_only:
            print("  [%2d] 0x%08X  %-12s %-14s %s"
                  % (j, va, name, rest[0] if rest else "",
                     ", ".join(p for p in paths)))
        else:
            print()
            print("  [%2d] VA 0x%08X" % (j, va))
            print("       display name   %s" % name)
            for p in paths:
                print("       texture path   %s" % p)
            for k, x in enumerate(rest):
                print("       field %-8d %s" % (k, x))

    print()
    print("=" * 78)
    print("records                     %d" % len(records))
    print("texture paths in them       %d" % total_paths)
    print("records with an edition tag %d" % sum(editions.values()))
    for k in sorted(editions):
        print("   edition %sa              %d" % (k, editions[k]))
    print("records with no tag         %d"
          % (len(records) - sum(editions.values())))


if __name__ == "__main__":
    main()
