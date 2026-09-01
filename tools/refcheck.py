#!/usr/bin/env python3
"""refcheck.py -- which paths named inside a binary are actually shipped.

The game executable names its data files as relative paths from
`bin/release`, with Windows separators, and it names some that are not on the
disc. This walks a strdump.py listing, pulls out every `..\\..\\`-rooted path,
resolves it case-insensitively against the extracted tree, and reports which
ones resolve and which do not.

Case-insensitivity matters and is not laziness: the executable writes
`..\\..\\media\\sound\\` in lower case while the shipped directory is
`media/Sound`. On Windows both work; on a case-sensitive filesystem, or in a
census that compares strings, they do not, and the difference would be read
as a missing file when it is only a missing shift key.

Usage:
    python tools/refcheck.py STRINGS.txt BASEDIR
"""
import os
import re
import sys

BS = chr(92)
# A backslash inside a character class has to be escaped, or `[\]` swallows
# the closing bracket and the pattern fails to compile. re.escape does it.
ESC = re.escape(BS)
PAT = re.compile(r"((?:\.\." + ESC + r")+[^\s]*?\.[A-Za-z0-9]{2,9})")


def resolve(base, rel):
    parts = rel.replace(BS, "/").split("/")
    cur = base
    for i, part in enumerate(parts):
        if part == "..":
            cur = os.path.dirname(cur)
            continue
        if not os.path.isdir(cur):
            return None
        match = None
        for name in os.listdir(cur):
            if name.lower() == part.lower():
                match = name
                break
        if match is None:
            return None
        cur = os.path.join(cur, match)
    return cur


def main():
    strings_file, base = sys.argv[1], sys.argv[2]
    refs = set()
    with open(strings_file, encoding="utf-8", errors="replace") as f:
        for line in f:
            for m in PAT.finditer(line):
                refs.add(m.group(1))
    present = absent = 0
    for r in sorted(refs):
        p = resolve(base, r)
        ok = p is not None and os.path.exists(p)
        present += ok
        absent += not ok
        print("  %-50s %s" % (r, "present" if ok else "ABSENT"))
    print()
    print("referenced paths : %d" % len(refs))
    print("present          : %d" % present)
    print("absent           : %d" % absent)


if __name__ == "__main__":
    main()
