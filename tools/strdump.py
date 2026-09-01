#!/usr/bin/env python3
"""A `strings` replacement, because this shell has none.

Prints runs of printable bytes with their file offset. Optionally accepts
high bytes (0x80..0xFF) inside a run and reports which ones occurred, which is
how accented characters get found without assuming an encoding; and optionally
reports Turbo Pascal style length-prefixed strings, where the byte before the
run equals the run length.

    python tools/strdump.py FILE [--min N] [--high] [--pascal] [--grep RE]
    python tools/strdump.py FILE --accent
    python tools/strdump.py FILE --utf16 [--min N] [--grep RE]

--utf16 finds UTF-16LE runs, which is where a Win32 binary keeps its resource
strings and its version block. On this disc the ASCII scan and the UTF-16 scan
find different things and both are needed.

--accent is the one that answers "are there accented characters?". Plain
--high does NOT: on an executable image, accepting 0x80..0xFF as run members
turns machine code into one enormous run and the census fills up with 0x8B,
0x89 and friends, which are `mov` opcodes and not letters. --accent instead
requires a byte in 0x80..0xFF to be surrounded by at least three ASCII letters
on each side, which is what a remapped or high-ASCII glyph inside real text
looks like and what a code byte almost never does.
"""
import re
import sys
from collections import Counter

PRINTABLE = set(range(0x20, 0x7F))


def runs(b, minlen, high):
    ok = PRINTABLE | (set(range(0x80, 0x100)) if high else set())
    cur, start = [], 0
    for i, x in enumerate(b):
        if x in ok:
            if not cur:
                start = i
            cur.append(x)
        else:
            if len(cur) >= minlen:
                yield start, bytes(cur)
            cur = []
    if len(cur) >= minlen:
        yield start, bytes(cur)


LETTERS = set(range(0x41, 0x5B)) | set(range(0x61, 0x7B)) | {0x20}


def accent_scan(b):
    """Bytes 0x80..0xFF with >=3 ASCII letters/spaces on each side."""
    hits = Counter()
    where = []
    for i in range(3, len(b) - 3):
        if b[i] < 0x80:
            continue
        before = all(x in LETTERS for x in b[i - 3:i])
        after = all(x in LETTERS for x in b[i + 1:i + 4])
        if before and after:
            hits[b[i]] += 1
            where.append(i)
    return hits, where


def utf16_runs(b, minlen):
    """UTF-16LE runs: an even-offset sequence of `xx 00` pairs with xx
    printable. Reported at both parities because a run can start at an odd
    file offset when a structure ahead of it is not word-aligned."""
    for parity in (0, 1):
        cur, start = [], 0
        i = parity
        while i + 1 < len(b):
            lo, hi = b[i], b[i + 1]
            if hi == 0 and (0x20 <= lo < 0x7F):
                if not cur:
                    start = i
                cur.append(lo)
            else:
                if len(cur) >= minlen:
                    yield start, bytes(cur)
                cur = []
            i += 2
        if len(cur) >= minlen:
            yield start, bytes(cur)


def main():
    path = sys.argv[1]
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except Exception:
        pass
    if "--utf16" in sys.argv:
        minlen = 4
        if "--min" in sys.argv:
            minlen = int(sys.argv[sys.argv.index("--min") + 1])
        pat = None
        if "--grep" in sys.argv:
            pat = re.compile(sys.argv[sys.argv.index("--grep") + 1], re.I)
        b = open(path, "rb").read()
        n = 0
        seen = set()
        for off, s2 in sorted(utf16_runs(b, minlen)):
            txt = s2.decode("latin-1")
            if pat and not pat.search(txt):
                continue
            if (off, txt) in seen:
                continue
            seen.add((off, txt))
            print("%08X  %s" % (off, txt))
            n += 1
        print()
        print("# %s: %d UTF-16LE runs, min length %d" % (path, n, minlen))
        return
    if "--accent" in sys.argv:
        b = open(path, "rb").read()
        hits, where = accent_scan(b)
        print(f"# {path}: bytes 0x80-0xFF embedded in ASCII text "
              f"(>=3 letters each side)")
        if not hits:
            print("#   none -- no accented or high-ASCII character appears "
                  "inside any text run")
        for x, c in sorted(hits.items()):
            print(f"#   0x{x:02X}  {c}")
        for off in where[:20]:
            ctx = b[off - 12:off + 12]
            print(f"    {off:08X}  " + "".join(
                chr(v) if 0x20 <= v < 0x7F else "[%02X]" % v for v in ctx))
        return
    minlen = 4
    high = "--high" in sys.argv
    pascal = "--pascal" in sys.argv
    pat = None
    if "--min" in sys.argv:
        minlen = int(sys.argv[sys.argv.index("--min") + 1])
    if "--grep" in sys.argv:
        pat = re.compile(sys.argv[sys.argv.index("--grep") + 1], re.I)
    b = open(path, "rb").read()

    hi = Counter()
    n = pas = 0
    for off, s in runs(b, minlen, high):
        txt = "".join(chr(x) if 0x20 <= x < 0x7F else f"\\x{x:02X}" for x in s)
        if pat and not pat.search(txt):
            continue
        mark = ""
        if off > 0 and b[off - 1] == len(s):
            mark = "  <-- pascal string[]"
            pas += 1
        for x in s:
            if x >= 0x80:
                hi[x] += 1
        if pascal and not mark:
            continue
        print(f"{off:08X}  {txt}{mark}")
        n += 1
    print(f"\n# {path}: {n} runs printed, min length {minlen}, "
          f"high bytes {'accepted' if high else 'rejected'}, "
          f"{pas} length-prefixed")
    if hi:
        print("# high-byte census (byte, count):")
        for x, c in sorted(hi.items()):
            print(f"#   0x{x:02X}  {c}")


if __name__ == "__main__":
    main()
