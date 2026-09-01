#!/usr/bin/env python3
"""hashall.py -- one line per file: sha1, size, path.

Written because the eighth session published pc-harrypotter4-doc/notes/
sha1-all.txt and that file turned a thirty-second measurement into something
possible without the other disc in the drive. This produces the same artefact
for this disc, in the same shape, so the next session gets the same courtesy.

The path printed is relative to ROOT and uses forward slashes, so two lists
made on two machines compare.

    python tools/hashall.py E:/ > notes/sha1-all.txt
    python tools/hashall.py E:/ --algo sha256
"""
import argparse
import hashlib
import os
import sys


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("root")
    ap.add_argument("--algo", default="sha1")
    a = ap.parse_args()

    root = a.root.rstrip("/").rstrip(chr(92))
    rows = []
    bad = []
    for r, dirs, names in os.walk(a.root):
        dirs.sort()
        for name in sorted(names):
            p = os.path.join(r, name)
            rel = os.path.relpath(p, a.root).replace(chr(92), "/")
            h = hashlib.new(a.algo)
            n = 0
            try:
                with open(p, "rb") as fh:
                    while True:
                        b = fh.read(1 << 22)
                        if not b:
                            break
                        h.update(b)
                        n += len(b)
            except OSError as e:
                # A disc with a physically unreadable region has files that
                # cannot be hashed. Saying so per file is the measurement;
                # dropping them silently would make the list look complete.
                bad.append((rel, n, e.strerror))
                print("UNREADABLE  %12d  %s   (%d bytes read, then %s)"
                      % (-1, rel, n, e.strerror))
                sys.stdout.flush()
                continue
            rows.append((h.hexdigest(), n, rel))
            print("%s  %12d  %s" % (h.hexdigest(), n, rel))
            sys.stdout.flush()
    total = sum(x[1] for x in rows)
    distinct = len({x[0] for x in rows})
    NL = chr(10)
    sys.stderr.write("files %d  bytes %d  distinct %s %d  unreadable %d" % (
        len(rows), total, a.algo, distinct, len(bad)) + NL)
    for rel, n, err in bad:
        sys.stderr.write("  UNREADABLE %s (%d bytes read, %s)" % (
            rel, n, err) + NL)


if __name__ == "__main__":
    main()
