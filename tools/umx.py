#!/usr/bin/env python3
"""umx.py -- what is inside the 91 music packages.

A .umx is an Unreal package holding one object of class Music. The format of
the payload is not guessed: it is named in the package's own name table, which
carries a lowercase format tag alongside the object name. This tool reports
that tag for every package first, and only then goes looking for the payload,
so the census does not depend on the extractor working.

THE ORACLE, decided before the extractor was written: whatever comes out must
begin with the signature its declared format requires --

    it    -> "IMPM"                       at offset 0
    s3m   -> "SCRM"                       at offset 44
    xm    -> "Extended Module: "          at offset 0
    mod   -> "M.K." / "M!K!" / "FLT4" ... at offset 1080
    mp2   -> an MPEG audio frame sync, 11 bits set, at offset 0
    wav   -> "RIFF" .... "WAVE"           at offset 0

If a payload comes out that does not satisfy its own declared format, the
extractor is wrong and the number is not reported.

    python tools/umx.py DIR --tags        format tag census, no extraction
    python tools/umx.py DIR --extract OUT
    python tools/umx.py FILE --probe
"""
import collections
import hashlib
import os
import struct
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
import upkg  # noqa: E402

MODMAGIC = (b"M.K.", b"M!K!", b"FLT4", b"FLT8", b"4CHN", b"6CHN", b"8CHN",
            b"CD81", b"OKTA", b"16CN", b"32CN")


def mpeg_frame(b, off=0):
    """True if a valid-looking MPEG audio frame header sits at off."""
    if len(b) < off + 4:
        return None
    if b[off] != 0xFF or (b[off + 1] & 0xE0) != 0xE0:
        return None
    ver = (b[off + 1] >> 3) & 3
    lay = (b[off + 1] >> 1) & 3
    if ver == 1 or lay == 0:
        return None
    vers = {0: "MPEG-2.5", 2: "MPEG-2", 3: "MPEG-1"}[ver]
    lays = {1: "Layer III", 2: "Layer II", 3: "Layer I"}[lay]
    br = (b[off + 2] >> 4) & 0xF
    sr = (b[off + 2] >> 2) & 3
    mode = (b[off + 3] >> 6) & 3
    modes = {0: "stereo", 1: "joint stereo", 2: "dual channel", 3: "mono"}
    return "%s %s, bitrate idx %d, samplerate idx %d, %s" % (
        vers, lays, br, sr, modes[mode])


def check(fmt, data):
    """The oracle. Returns (ok, note)."""
    f = fmt.lower()
    if f == "it":
        return data[:4] == b"IMPM", "IMPM at 0: %r" % data[:4]
    if f == "s3m":
        return data[44:48] == b"SCRM", "SCRM at 44: %r" % data[44:48]
    if f == "xm":
        return data[:17] == b"Extended Module: ", "at 0: %r" % data[:17]
    if f == "mod":
        return data[1080:1084] in MODMAGIC, "at 1080: %r" % data[1080:1084]
    if f in ("mp2", "mp3"):
        m = mpeg_frame(data, 0)
        return m is not None, (m or "no MPEG sync at 0: %r" % data[:4])
    if f == "wav":
        return (data[:4] == b"RIFF" and data[8:12] == b"WAVE"), \
            "%r ... %r" % (data[:4], data[8:12])
    return False, "no oracle registered for format %r" % fmt


def tag_of(p):
    """The format tag: the name-table entry that is not a class, package or
    object name. Measured, not assumed: it is the entry that is all-lowercase,
    short, and not referenced by any import or export."""
    used = set()
    for cp, cn, pk, on in p.imports:
        used.update((cp, cn, on))
    for e in p.exports:
        used.add(e[3])
    cand = [(i, s) for i, s in enumerate(p.names)
            if i not in used and s and s == s.lower() and len(s) <= 8]
    return cand


def payload(p):
    """Find the Music export's payload. Returns (fmt, offset, bytes)."""
    p.load()
    cand = tag_of(p)
    fmt = cand[0][1] if cand else None
    mus = None
    for e in p.exports:
        r = e[0]
        cls = ""
        if r < 0 and -r - 1 < len(p.imports):
            cls = p.name(p.imports[-r - 1][3])
        if cls == "Music":
            mus = e
            break
    if mus is None:
        return fmt, None, None, "no export of class Music"
    ssz, soff = mus[5], mus[6]
    blob = p.d[soff:soff + ssz]
    # walk candidate starts: the payload begins within the first 64 bytes,
    # after the property terminator and a small header. Try every offset and
    # keep the first that satisfies the declared format's oracle.
    for start in range(0, min(64, len(blob))):
        ok, note = check(fmt or "", blob[start:])
        if ok:
            return fmt, soff + start, blob[start:], note
    return fmt, None, blob, "no offset in 0..63 satisfies the %r oracle" % fmt


def main():
    args = sys.argv[1:]
    if not args:
        raise SystemExit(__doc__)
    target = args[0]
    paths = []
    if os.path.isfile(target):
        paths = [target]
    else:
        for dp, dn, fn in os.walk(target):
            for f in sorted(fn):
                if f.lower().endswith(".umx"):
                    paths.append(os.path.join(dp, f))

    if "--tags" in args:
        tags = collections.Counter()
        print("%-40s %5s %8s %7s %-8s  %s"
              % ("package", "ver", "bytes", "names", "tag", "name table"))
        for path in paths:
            p = upkg.Package(path)
            p.load()
            cand = tag_of(p)
            tag = cand[0][1] if cand else "(none)"
            tags[tag] += 1
            print("%-40s %5d %8d %7d %-8s  %s"
                  % (os.path.basename(path), p.ver, p.size, p.name_n, tag,
                     " ".join(p.names)))
        print()
        print("format tag census over %d packages:" % len(paths))
        for t, n in tags.most_common():
            print("   %-10s %d" % (t, n))
        return

    if "--probe" in args:
        p = upkg.Package(target)
        fmt, off, data, note = payload(p)
        print("package : %s" % target)
        print("version : %d" % p.ver)
        print("names   : %s" % p.names)
        print("tag     : %r" % fmt)
        print("payload : offset %s, %s bytes"
              % (off, len(data) if data is not None else "-"))
        print("oracle  : %s" % note)
        if data:
            print("first 64 bytes:")
            for a in range(0, 64, 16):
                ch = data[a:a + 16]
                print("   %4d  %-47s  %s"
                      % (a, ch.hex(" "),
                         "".join(chr(c) if 32 <= c < 127 else "." for c in ch)))
        return

    out = None
    if "--extract" in args:
        out = args[args.index("--extract") + 1]
        os.makedirs(out, exist_ok=True)

    ok = fail = 0
    digests = collections.Counter()
    where = collections.defaultdict(list)
    fmts = collections.Counter()
    total = 0
    print("%-40s %-6s %9s %9s %-7s %s"
          % ("package", "tag", "pkg bytes", "payload", "verdict", "note"))
    for path in paths:
        p = upkg.Package(path)
        fmt, off, data, note = payload(p)
        if data is None or off is None:
            print("%-40s %-6s %9d %9s %-7s %s"
                  % (os.path.basename(path), fmt, p.size, "-", "FAIL", note))
            fail += 1
            continue
        ok += 1
        fmts[fmt] += 1
        total += len(data)
        h = hashlib.sha1(data).hexdigest()
        digests[h] += 1
        where[h].append(os.path.basename(path))
        print("%-40s %-6s %9d %9d %-7s %s"
              % (os.path.basename(path), fmt, p.size, len(data), "ok", note))
        if out:
            base = os.path.splitext(os.path.basename(path))[0]
            with open(os.path.join(out, base + "." + (fmt or "bin")), "wb") as f:
                f.write(data)
    print()
    print("packages          : %d" % len(paths))
    print("payload extracted : %d" % ok)
    print("oracle failures   : %d" % fail)
    print("format tags       : %s" % dict(fmts))
    print("payload bytes     : %d" % total)
    print("package bytes     : %d" % sum(os.path.getsize(x) for x in paths))
    if paths:
        print("payload share     : %.3f %%"
              % (100.0 * total / sum(os.path.getsize(x) for x in paths)))
    print()
    print("distinct payloads by SHA-1: %d of %d" % (len(digests), ok))
    dup = [(h, n) for h, n in digests.items() if n > 1]
    if not dup:
        print("no two packages carry the same payload.")
    for h, n in sorted(dup, key=lambda x: -x[1]):
        print("   x%d  %s  %s" % (n, h[:16], ", ".join(where[h])))


if __name__ == "__main__":
    main()
