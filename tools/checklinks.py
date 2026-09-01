#!/usr/bin/env python3
"""checklinks.py -- every relative link in every document resolves.

Run before committing, not after. A broken link in a repository whose whole
claim is that each number has a command behind it is the same class of error as
a number without a command.

Also checks that fenced code blocks come in pairs, because an odd count turns
the rest of a document into one code block and nothing renders.

    python tools/checklinks.py
"""
import os
import re
import sys

LINK = re.compile(r"\[([^\]]*)\]\(([^)]+)\)")


def main():
    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    docs = []
    for dp, dn, fn in os.walk(root):
        if os.sep + ".git" in dp or "_work" in dp:
            continue
        for f in sorted(fn):
            if f.endswith(".md"):
                docs.append(os.path.join(dp, f))

    print("markdown files: %d" % len(docs))
    print()
    bad = 0
    checked = 0
    for d in docs:
        text = open(d, encoding="utf-8").read()
        rel = os.path.relpath(d, root).replace(os.sep, "/")

        fences = text.count("\n```")
        if text.startswith("```"):
            fences += 1
        if fences % 2:
            print("  ODD FENCE COUNT (%d) in %s" % (fences, rel))
            bad += 1

        for label, target in (m.groups() for m in LINK.finditer(text)):
            if target.startswith(("http://", "https://", "#", "mailto:")):
                continue
            t = target.split("#")[0]
            if not t:
                continue
            p = os.path.normpath(os.path.join(os.path.dirname(d), t))
            checked += 1
            if not os.path.exists(p):
                print("  BROKEN  %s -> %s   (label %r)" % (rel, target, label))
                bad += 1

    print()
    print("relative links checked : %d" % checked)
    print("problems               : %d" % bad)
    return 1 if bad else 0


if __name__ == "__main__":
    sys.exit(main())
