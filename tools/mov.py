#!/usr/bin/env python3
"""mov.py -- walk QuickTime atom trees. Structure, codecs, dates, no decoding.

Nineteen `.mov` files are 53.29 % of this tree, and the interesting questions
about them are all structural:

  * `HIntro.Mov` begins with `mdat` and `VIDEO_01.mov` begins with `moov`. A
    file whose movie header precedes its media data can start playing before
    it has finished downloading; one whose header is at the end cannot. The
    order is set by whether somebody ran a "flatten / make self-contained,
    optimised for web" pass, so counting the split counts production passes;
  * the `mvhd` and `tkhd` atoms carry creation and modification times as
    seconds since 1904-01-01 UTC. That is a clock **inside** the file, written
    by the authoring application, and it is independent of the filesystem
    mtime that the copy preserved. Where two clocks disagree, something has to
    give, and this repository has a disagreement to settle;
  * `stsd` names the codec as a four-character code, per track.

Everything is walked from byte 0 through each atom's own size field. A 64-bit
size (size == 1) is read from the eight bytes after the type. size == 0 means
"to end of file". Atoms are never searched for by magic: `moov` occurs inside
compressed video data often enough to invent whole phantom movies.

The 1904 epoch is the trap. QuickTime counts from 1904-01-01 00:00:00 UTC,
which is 2,082,844,800 seconds before the Unix epoch. Read it as Unix time and
every date lands in 2036 and looks like an overflow bug. Read it as local time
and it drifts by the authoring machine's offset -- which is exactly what makes
it comparable to a FAT mtime, so both are printed.

    python tools/mov.py FILE [FILE...]
    python tools/mov.py FILE --tree
    python tools/mov.py DIR --recurse
    python tools/mov.py DIR --recurse --summary
"""
import argparse
import datetime
import os
import struct
import sys

QT_EPOCH_DELTA = 2082844800          # seconds between 1904-01-01 and 1970-01-01

CONTAINERS = {
    b"moov", b"trak", b"edts", b"mdia", b"minf", b"dinf", b"stbl", b"udta",
    b"clip", b"matt", b"rmra", b"rmda", b"gmhd", b"tref", b"meta",
}

HANDLERS = {b"vide": "video", b"soun": "sound", b"text": "text",
            b"tmcd": "timecode", b"musi": "music", b"qtvr": "QTVR",
            b"pano": "panorama", b"hint": "hint"}


def qt_time(v):
    """A QuickTime 1904-epoch seconds value as a naive UTC datetime, or None."""
    if not v:
        return None
    try:
        return datetime.datetime(1904, 1, 1) + datetime.timedelta(seconds=v)
    except (OverflowError, ValueError):
        return None


def fmt_time(v):
    d = qt_time(v)
    return d.strftime("%Y-%m-%d %H:%M:%S") if d else "(zero/invalid: %d)" % v


def atoms(data, start, end, depth=0):
    """Yield (offset, size, type, header_len, depth) for atoms in [start,end)."""
    pos = start
    while pos + 8 <= end:
        size = struct.unpack_from(">I", data, pos)[0]
        atype = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1:
            if pos + 16 > end:
                return
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            hdr = 16
        elif size == 0:
            size = end - pos
        if size < hdr or pos + size > end:
            # A short or overlong atom is a finding, not something to recover
            # from by rescanning. Report and stop walking this level.
            yield pos, size, atype, hdr, depth
            return
        yield pos, size, atype, hdr, depth
        if atype in CONTAINERS:
            for a in atoms(data, pos + hdr, pos + size, depth + 1):
                yield a
        pos += size


def describe(path, tree=False):
    data = open(path, "rb").read()
    n = len(data)
    info = {"path": path, "size": n}

    top = []
    pos = 0
    while pos + 8 <= n:
        size = struct.unpack_from(">I", data, pos)[0]
        atype = data[pos + 4:pos + 8]
        hdr = 8
        if size == 1:
            size = struct.unpack_from(">Q", data, pos + 8)[0]
            hdr = 16
        elif size == 0:
            size = n - pos
        if size < hdr or pos + size > n:
            top.append((pos, size, atype, "TRUNCATED/BAD"))
            break
        top.append((pos, size, atype, ""))
        pos += size

    info["first_atom"] = top[0][2] if top else b"????"
    info["top_atoms"] = [(t[2], t[1]) for t in top]
    info["fast_start"] = bool(top) and top[0][2] == b"moov"

    mvhd = None
    tracks = []
    cur = None
    for off, size, atype, hdr, depth in atoms(data, 0, n):
        body = off + hdr
        if atype == b"mvhd":
            ver = data[body]
            if ver == 0:
                ct, mt, scale, dur = struct.unpack_from(">IIII", data, body + 4)
            else:
                ct, mt = struct.unpack_from(">QQ", data, body + 4)
                scale, dur = struct.unpack_from(">IQ", data, body + 20)[0], \
                    struct.unpack_from(">Q", data, body + 24)[0]
            mvhd = {"created": ct, "modified": mt, "scale": scale, "dur": dur}
        elif atype == b"trak":
            cur = {"codecs": [], "handler": None, "dur": 0, "scale": 0}
            tracks.append(cur)
        elif atype == b"tkhd" and cur is not None:
            ver = data[body]
            if ver == 0:
                ct, mt, tid, _r, dur = struct.unpack_from(">IIIII", data, body + 4)
            else:
                ct, mt = struct.unpack_from(">QQ", data, body + 4)
                dur = 0
            cur["created"], cur["modified"] = ct, mt
        elif atype == b"mdhd" and cur is not None:
            ver = data[body]
            if ver == 0:
                ct, mt, scale, dur = struct.unpack_from(">IIII", data, body + 4)
            else:
                ct, mt = struct.unpack_from(">QQ", data, body + 4)
                scale = struct.unpack_from(">I", data, body + 20)[0]
                dur = struct.unpack_from(">Q", data, body + 24)[0]
            cur["scale"], cur["dur"] = scale, dur
        elif atype == b"hdlr" and cur is not None:
            comp = data[body + 8:body + 12]
            if comp in HANDLERS and cur["handler"] is None:
                cur["handler"] = comp
        elif atype == b"stsd" and cur is not None:
            cnt = struct.unpack_from(">I", data, body + 4)[0]
            p = body + 8
            for _ in range(min(cnt, 16)):
                if p + 8 > n:
                    break
                esize = struct.unpack_from(">I", data, p)[0]
                cur["codecs"].append(data[p + 4:p + 8])
                if esize <= 0:
                    break
                p += esize

    info["mvhd"] = mvhd
    info["tracks"] = tracks
    if mvhd and mvhd["scale"]:
        info["duration"] = mvhd["dur"] / float(mvhd["scale"])
    else:
        info["duration"] = 0.0

    print("file            : %s" % path)
    print("size            : %d bytes" % n)
    print("top-level atoms : %s"
          % " ".join("%s(%d)" % (t[0].decode("latin-1", "replace"), t[1])
                     for t in info["top_atoms"]))
    print("first atom      : %s   -> %s"
          % (info["first_atom"].decode("latin-1", "replace"),
             "fast-start (moov before mdat)" if info["fast_start"]
             else "NOT fast-start (media before header)"))
    if mvhd:
        print("mvhd timescale  : %d, duration %d units = %.3f s"
              % (mvhd["scale"], mvhd["dur"], info["duration"]))
        print("mvhd created    : %s  (1904 epoch, read as UTC)"
              % fmt_time(mvhd["created"]))
        print("mvhd modified   : %s" % fmt_time(mvhd["modified"]))
    print("tracks          : %d" % len(tracks))
    for i, t in enumerate(tracks):
        d = t["dur"] / float(t["scale"]) if t.get("scale") else 0.0
        print("    [%d] %-9s %-8s codecs %s"
              % (i,
                 HANDLERS.get(t["handler"], "?") if t["handler"] else "?",
                 "%.2fs" % d,
                 " ".join(c.decode("latin-1", "replace") for c in t["codecs"])))
    if tree:
        print()
        for off, size, atype, hdr, depth in atoms(data, 0, n):
            print("%s%s  %d bytes at %d"
                  % ("  " * depth, atype.decode("latin-1", "replace"), size, off))
    return info


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("paths", nargs="+")
    ap.add_argument("--tree", action="store_true")
    ap.add_argument("--recurse", action="store_true")
    ap.add_argument("--summary", action="store_true")
    args = ap.parse_args()
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="backslashreplace")
    except (AttributeError, ValueError):
        pass

    files = []
    for p in args.paths:
        if os.path.isdir(p) and args.recurse:
            for dp, dn, fn in os.walk(p):
                dn.sort()
                for f in sorted(fn):
                    if f.lower().endswith((".mov", ".qt")):
                        files.append(os.path.join(dp, f))
        else:
            files.append(p)

    infos = []
    for i, f in enumerate(files):
        if not args.summary:
            if i:
                print()
            infos.append(describe(f, args.tree))
        else:
            import io as _io
            buf = _io.StringIO()
            old = sys.stdout
            sys.stdout = buf
            try:
                infos.append(describe(f, False))
            finally:
                sys.stdout = old

    if args.summary:
        print("%-28s %11s %8s %9s %-10s %-18s %s"
              % ("file", "bytes", "first", "duration", "video", "audio", "mvhd created"))
        print("-" * 28 + " " + "-" * 11 + " " + "-" * 8 + " " + "-" * 9 + " "
              + "-" * 10 + " " + "-" * 18 + " " + "-" * 19)
        for inf in infos:
            v = a = ""
            for t in inf["tracks"]:
                cs = " ".join(c.decode("latin-1", "replace") for c in t["codecs"])
                if t["handler"] == b"vide":
                    v = cs
                elif t["handler"] == b"soun":
                    a = cs
            print("%-28s %11d %8s %8.2fs %-10s %-18s %s"
                  % (os.path.basename(inf["path"]), inf["size"],
                     inf["first_atom"].decode("latin-1", "replace"),
                     inf["duration"], v, a,
                     fmt_time(inf["mvhd"]["created"]) if inf["mvhd"] else "-"))
        print()
        fast = sum(1 for i in infos if i["fast_start"])
        print("files                 : %d" % len(infos))
        print("fast-start (moov 1st) : %d" % fast)
        print("not fast-start        : %d" % (len(infos) - fast))
        print("total bytes           : %d" % sum(i["size"] for i in infos))
        print("total duration        : %.2f s = %.2f min"
              % (sum(i["duration"] for i in infos),
                 sum(i["duration"] for i in infos) / 60.0))


if __name__ == "__main__":
    main()
